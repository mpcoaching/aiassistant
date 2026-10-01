import assert from 'node:assert';
import test from 'node:test';
import { IExecuteFunctions, INodeExecutionData } from 'n8n-workflow';
import { Result } from './Result.node';

type TestItem = {
	json: Record<string, unknown>;
	binary?: Record<string, unknown>;
	metadata?: Record<string, unknown>;
	pairedItem?: { item: number };
};

type NodeParameters = Record<string, unknown>;

/**
 * Defaults declared on the node description. The fake getNodeParameter falls
 * back to these, so a test that omits a parameter exercises the same value n8n
 * would supply for a node saved before that parameter existed.
 */
const propertyDefaults = new Map<string, unknown>(
	(new Result().description.properties as Array<{ name: string; default?: unknown }>).map(
		(property) => [property.name, property.default],
	),
);

function makeExecute(resultSource: unknown, targetPath: unknown, extra: NodeParameters = {}) {
	const params: NodeParameters = { resultSource, targetPath, ...extra };
	let resultItems: TestItem[] = [];
	let payloadItems: TestItem[] = [];
	const fakeThis = {
		getInputData(inputIndex = 0): TestItem[] {
			return inputIndex === 0 ? resultItems : payloadItems;
		},
		getNodeParameter(name: string) {
			if (name in params) {
				return params[name];
			}
			return propertyDefaults.get(name) ?? '';
		},
		getNode() {
			return { name: 'Result' };
		},
	};
	return {
		execute: Result.prototype.execute.bind(fakeThis as unknown as IExecuteFunctions),
		setInputs(results: TestItem[], payloads: TestItem[]) {
			resultItems = results;
			payloadItems = payloads;
		},
	};
}

function snapshot(value: unknown): string {
	return JSON.stringify(value);
}

const description = new Result().description;
const inputs = description.inputs as Array<{ type: string; displayName?: string }>;
const outputs = description.outputs as unknown[];

const RESULT_A = { foo: 'bar', status: 'completed' };
const PAYLOAD_A = { customer: '123', request: 'do something' };

/** The conceptual message shape the history feature appends into. */
const MESSAGE_A = {
	event: { type: 'greeting', id: 'e-1' },
	context: { stack: [{ node: 'start' }] },
	result: {},
};
const MESSAGE_B = {
	event: { type: 'farewell', id: 'e-2' },
	context: { stack: [{ node: 'start' }, { node: 'middle' }] },
	result: {},
};

const tests: Array<{ name: string; run: () => Promise<void> | void }> = [
	{
		name: 'writes the entire RESULT item when resultSource is empty (example 1)',
		run: async () => {
			const { execute, setInputs } = makeExecute('', 'ginaNode');
			setInputs([{ json: RESULT_A }], [{ json: PAYLOAD_A }]);

			const output = (await execute())[0];

			assert.strictEqual(output.length, 1);
			assert.deepStrictEqual(output[0].json, {
				customer: '123',
				request: 'do something',
				ginaNode: { foo: 'bar', status: 'completed' },
			});
		},
	},
	{
		name: 'writes the selected RESULT value when resultSource is supplied (example 2)',
		run: async () => {
			const { execute, setInputs } = makeExecute('status', 'ginaNode.result');
			setInputs([{ json: RESULT_A }], [{ json: PAYLOAD_A }]);

			const output = (await execute())[0];

			assert.deepStrictEqual(output[0].json, {
				customer: '123',
				request: 'do something',
				ginaNode: { result: 'completed' },
			});
		},
	},
	{
		name: 'resolves a nested dot-notation resultSource',
		run: async () => {
			const { execute, setInputs } = makeExecute('data.result.value', 'ginaNode.deep.value');
			setInputs(
				[{ json: { data: { result: { value: 7, ignored: true } } } }],
				[{ json: { customer: '123' } }],
			);

			const output = (await execute())[0];

			assert.deepStrictEqual(output[0].json, {
				customer: '123',
				ginaNode: { deep: { value: 7 } },
			});
		},
	},
	{
		name: 'creates intermediate objects for a nested dot-notation targetPath',
		run: async () => {
			const { execute, setInputs } = makeExecute('', 'a.b.c.d');
			setInputs([{ json: RESULT_A }], [{ json: { customer: '123' } }]);

			const output = (await execute())[0];

			assert.deepStrictEqual(output[0].json, {
				customer: '123',
				a: { b: { c: { d: { foo: 'bar', status: 'completed' } } } },
			});
		},
	},
	{
		name: 'preserves existing top-level payload fields',
		run: async () => {
			const { execute, setInputs } = makeExecute('status', 'ginaNode.result');
			setInputs([{ json: RESULT_A }], [
				{ json: { customer: '123', request: 'do something', meta: { source: 'crm' } } },
			]);

			const output = (await execute())[0];

			assert.deepStrictEqual(output[0].json, {
				customer: '123',
				request: 'do something',
				meta: { source: 'crm' },
				ginaNode: { result: 'completed' },
			});
		},
	},
	{
		name: 'preserves existing results while adding a new one',
		run: async () => {
			const { execute, setInputs } = makeExecute('value', 'ginaNode.newResult');
			setInputs(
				[{ json: { value: 42 } }],
				[{ json: { customer: '123', ginaNode: { previousResult: 'already here' } } }],
			);

			const output = (await execute())[0];

			assert.deepStrictEqual(output[0].json, {
				customer: '123',
				ginaNode: { previousResult: 'already here', newResult: 42 },
			});
		},
	},
	{
		name: 'accumulates across two chained Result nodes',
		run: async () => {
			// Operation A: `{ customer: '123' }` + `{ value: 42 }` at `ginaNode.operationA`
			const first = makeExecute('value', 'ginaNode.operationA');
			first.setInputs([{ json: { value: 42 } }], [{ json: { customer: '123' } }]);
			const afterA = (await first.execute())[0];

			// Operation B receives the accumulated payload from A.
			const second = makeExecute('value', 'ginaNode.operationB');
			second.setInputs([{ json: { value: 99 } }], afterA as unknown as TestItem[]);
			const afterB = (await second.execute())[0];

			assert.deepStrictEqual(afterB[0].json, {
				customer: '123',
				ginaNode: { operationA: 42, operationB: 99 },
			});
		},
	},
	{
		name: 'accumulates whole RESULT items across chained Result nodes',
		run: async () => {
			const first = makeExecute('', 'ginaNode.operationA');
			first.setInputs([{ json: { value: 42 } }], [{ json: { customer: '123' } }]);
			const afterA = (await first.execute())[0];

			const second = makeExecute('', 'ginaNode.operationB');
			second.setInputs([{ json: { value: 99 } }], afterA as unknown as TestItem[]);
			const afterB = (await second.execute())[0];

			assert.deepStrictEqual(afterB[0].json, {
				customer: '123',
				ginaNode: { operationA: { value: 42 }, operationB: { value: 99 } },
			});
		},
	},
	{
		name: 'overwrites an existing value at targetPath',
		run: async () => {
			const { execute, setInputs } = makeExecute('status', 'ginaNode.result');
			setInputs(
				[{ json: RESULT_A }],
				[{ json: { customer: '123', ginaNode: { result: 'old', keep: 'me' } } }],
			);

			const output = (await execute())[0];

			assert.deepStrictEqual(output[0].json, {
				customer: '123',
				ginaNode: { result: 'completed', keep: 'me' },
			});
		},
	},
	{
		name: 'overwrites an existing whole-object target when resultSource is empty',
		run: async () => {
			const { execute, setInputs } = makeExecute('', 'ginaNode');
			setInputs(
				[{ json: RESULT_A }],
				[{ json: { customer: '123', ginaNode: { previous: 'stale' } } }],
			);

			const output = (await execute())[0];

			assert.deepStrictEqual(output[0].json, {
				customer: '123',
				ginaNode: { foo: 'bar', status: 'completed' },
			});
		},
	},
	{
		name: 'replaces a non-object sitting on an intermediate target path',
		run: async () => {
			const { execute, setInputs } = makeExecute('value', 'ginaNode.result.deep');
			setInputs([{ json: { value: 1 } }], [{ json: { ginaNode: 'not-an-object' } }]);

			const output = (await execute())[0];

			assert.deepStrictEqual(output[0].json, { ginaNode: { result: { deep: 1 } } });
		},
	},
	{
		name: 'does not mutate the RESULT or PAYLOAD input items',
		run: async () => {
			const { execute, setInputs } = makeExecute('', 'ginaNode.result');
			const resultItem: TestItem = { json: { foo: 'bar', status: 'completed' } };
			const payloadItem: TestItem = { json: { customer: '123', ginaNode: { previous: 'x' } } };
			const resultBefore = snapshot(resultItem.json);
			const payloadBefore = snapshot(payloadItem.json);

			setInputs([resultItem], [payloadItem]);
			const output = (await execute())[0];

			assert.strictEqual(snapshot(resultItem.json), resultBefore);
			assert.strictEqual(snapshot(payloadItem.json), payloadBefore);
			// The output shares no object references with either input.
			assert.notStrictEqual(output[0].json, payloadItem.json);
			assert.notStrictEqual(
				(output[0].json as { ginaNode: unknown }).ginaNode,
				(payloadItem.json as { ginaNode: unknown }).ginaNode,
			);
			assert.deepStrictEqual(output[0].json, {
				customer: '123',
				ginaNode: { previous: 'x', result: { foo: 'bar', status: 'completed' } },
			});
		},
	},
	{
		name: 'copies the whole RESULT item without aliasing the RESULT item',
		run: async () => {
			const { execute, setInputs } = makeExecute('', 'ginaNode');
			const resultItem: TestItem = { json: { foo: 'bar', nested: { n: 1 } } };
			setInputs([resultItem], [{ json: { customer: '123' } }]);

			const output = (await execute())[0];
			const copied = (output[0].json as { ginaNode: { nested: unknown } }).ginaNode;

			assert.deepStrictEqual(copied, { foo: 'bar', nested: { n: 1 } });
			assert.notStrictEqual(copied, resultItem.json);
			assert.notStrictEqual(copied.nested, (resultItem.json as { nested: unknown }).nested);
		},
	},
	{
		name: 'copies a selected object value without aliasing the RESULT item',
		run: async () => {
			const { execute, setInputs } = makeExecute('data', 'ginaNode.copied');
			const resultItem: TestItem = { json: { data: { inner: { n: 1 } } } };
			setInputs([resultItem], [{ json: { customer: '123' } }]);

			const output = (await execute())[0];
			const copied = (output[0].json as { ginaNode: { copied: { inner: unknown } } }).ginaNode.copied;

			assert.deepStrictEqual(copied, { inner: { n: 1 } });
			assert.notStrictEqual(copied, (resultItem.json.data as { inner: unknown }).inner);
		},
	},
	{
		name: 'copies primitives, arrays, null and false values',
		run: async () => {
			const { execute, setInputs } = makeExecute('value', 'ginaNode.copied');
			setInputs(
				[
					{ json: { value: 'text' } },
					{ json: { value: 0 } },
					{ json: { value: false } },
					{ json: { value: null } },
					{ json: { value: [1, 2, 3] } },
				],
				[
					{ json: { i: 0 } },
					{ json: { i: 1 } },
					{ json: { i: 2 } },
					{ json: { i: 3 } },
					{ json: { i: 4 } },
				],
			);

			const output = (await execute())[0];

			assert.deepStrictEqual(
				output.map((item) => (item.json as { ginaNode: { copied: unknown } }).ginaNode.copied),
				['text', 0, false, null, [1, 2, 3]],
			);
		},
	},
	{
		name: 'pairs multiple items by index',
		run: async () => {
			const { execute, setInputs } = makeExecute('value', 'ginaNode.copied');
			setInputs(
				[{ json: { value: 1 } }, { json: { value: 2 } }, { json: { value: 3 } }],
				[{ json: { customer: 'a' } }, { json: { customer: 'b' } }, { json: { customer: 'c' } }],
			);

			const output = (await execute())[0];

			assert.strictEqual(output.length, 3);
			assert.deepStrictEqual(output[0].json, { customer: 'a', ginaNode: { copied: 1 } });
			assert.deepStrictEqual(output[1].json, { customer: 'b', ginaNode: { copied: 2 } });
			assert.deepStrictEqual(output[2].json, { customer: 'c', ginaNode: { copied: 3 } });
		},
	},
	{
		name: 'passes through PAYLOAD items that have no corresponding RESULT item',
		run: async () => {
			const { execute, setInputs } = makeExecute('value', 'ginaNode.copied');
			setInputs(
				[{ json: { value: 1 } }, { json: { value: 2 } }],
				[
					{ json: { customer: 'a' } },
					{ json: { customer: 'b' } },
					{ json: { customer: 'c' } },
				],
			);

			const output = (await execute())[0];

			// One output item per PAYLOAD item; the extra PAYLOAD item is unchanged.
			assert.strictEqual(output.length, 3);
			assert.deepStrictEqual(output[2].json, { customer: 'c' });
		},
	},
	{
		name: 'drops surplus RESULT items when there are fewer PAYLOAD items',
		run: async () => {
			const { execute, setInputs } = makeExecute('value', 'ginaNode.copied');
			setInputs(
				[{ json: { value: 1 } }, { json: { value: 2 } }, { json: { value: 3 } }],
				[{ json: { customer: 'a' } }],
			);

			const output = (await execute())[0];

			assert.strictEqual(output.length, 1);
			assert.deepStrictEqual(output[0].json, { customer: 'a', ginaNode: { copied: 1 } });
		},
	},
	{
		name: 'returns no items when the PAYLOAD input is empty',
		run: async () => {
			const { execute, setInputs } = makeExecute('value', 'ginaNode.copied');
			setInputs([{ json: { value: 1 } }], []);

			const output = (await execute())[0];

			assert.deepStrictEqual(output, []);
		},
	},
	{
		name: 'returns PAYLOAD items unchanged when the RESULT input is empty',
		run: async () => {
			const { execute, setInputs } = makeExecute('value', 'ginaNode.copied');
			setInputs([], [{ json: { customer: 'a' } }]);

			const output = (await execute())[0];

			assert.strictEqual(output.length, 1);
			assert.deepStrictEqual(output[0].json, { customer: 'a' });
		},
	},
	{
		name: 'throws when targetPath is empty',
		run: async () => {
			const { execute, setInputs } = makeExecute('value', '');
			setInputs([{ json: { value: 1 } }], [{ json: { customer: 'a' } }]);

			await assert.rejects(execute(), /'Target Path' must be a non-empty/);
		},
	},
	{
		name: 'throws when targetPath contains only separators and whitespace',
		run: async () => {
			const { execute, setInputs } = makeExecute('value', ' . . ');
			setInputs([{ json: { value: 1 } }], [{ json: { customer: 'a' } }]);

			await assert.rejects(execute(), /'Target Path' must be a non-empty/);
		},
	},
	{
		name: 'throws when targetPath is not a string',
		run: async () => {
			const { execute, setInputs } = makeExecute('value', null);
			setInputs([{ json: { value: 1 } }], [{ json: { customer: 'a' } }]);

			await assert.rejects(execute(), /'Target Path' must be a non-empty/);
		},
	},
	{
		name: 'throws when a supplied resultSource path is absent from a RESULT item',
		run: async () => {
			const { execute, setInputs } = makeExecute('missing.path', 'ginaNode.copied');
			setInputs(
				[{ json: { missing: { path: 1 } } }, { json: { other: 2 } }],
				[{ json: { customer: 'a' } }, { json: { customer: 'b' } }],
			);

			await assert.rejects(
				execute(),
				/RESULT item 1 has no value at the configured Result Source/,
			);
		},
	},
	{
		name: 'treats a non-string resultSource as unset and writes the whole RESULT item',
		run: async () => {
			const { execute, setInputs } = makeExecute(42, 'ginaNode');
			setInputs([{ json: RESULT_A }], [{ json: PAYLOAD_A }]);

			const output = (await execute())[0];

			assert.deepStrictEqual(output[0].json, {
				customer: '123',
				request: 'do something',
				ginaNode: { foo: 'bar', status: 'completed' },
			});
		},
	},
	{
		name: 'trims whitespace around dot-notation path segments',
		run: async () => {
			const { execute, setInputs } = makeExecute('  data . value ', ' ginaNode . copied ');
			setInputs([{ json: { data: { value: 3 } } }], [{ json: { customer: 'a' } }]);

			const output = (await execute())[0];

			assert.deepStrictEqual(output[0].json, { customer: 'a', ginaNode: { copied: 3 } });
		},
	},
	{
		name: 'preserves PAYLOAD binary, metadata and paired item and does not merge RESULT binary',
		run: async () => {
			const { execute, setInputs } = makeExecute('', 'ginaNode');
			setInputs(
				[{ json: RESULT_A, binary: { resultFile: { data: 'cmVzdWx0' } } }],
				[
					{
						json: PAYLOAD_A,
						binary: { file: { data: 'cGF5bG9hZA==' } },
						metadata: { subExecution: { id: 'x' } },
						pairedItem: { item: 3 },
					},
				],
			);

			const output = (await execute())[0];
			const item = output[0] as INodeExecutionData & { pairedItem?: { item: number } };

			assert.deepStrictEqual(item.binary, { file: { data: 'cGF5bG9hZA==' } });
			assert.deepStrictEqual(item.metadata, { subExecution: { id: 'x' } });
			assert.deepStrictEqual(item.pairedItem, { item: 3 });
			assert.deepStrictEqual(output[0].json, {
				customer: '123',
				request: 'do something',
				ginaNode: { foo: 'bar', status: 'completed' },
			});
		},
	},
	{
		name: 'does not let a prototype-polluting targetPath segment pollute Object.prototype',
		run: async () => {
			const { execute, setInputs } = makeExecute('', '__proto__.polluted');
			setInputs([{ json: RESULT_A }], [{ json: PAYLOAD_A }]);

			await execute();

			assert.strictEqual(
				(Object.prototype as unknown as Record<string, unknown>).polluted,
				undefined,
				'Object.prototype must not gain a "polluted" property',
			);
			assert.strictEqual(
				({} as Record<string, unknown>).polluted,
				undefined,
				'a freshly created object literal must not inherit "polluted"',
			);
		},
	},
	{
		name: 'node description exposes two labelled main inputs and one main output',
		run: () => {
			assert.strictEqual(inputs.length, 2);
			assert.strictEqual(outputs.length, 1);
			assert.deepStrictEqual(
				inputs.map((input) => input.type),
				['main', 'main'],
			);
			assert.deepStrictEqual(
				inputs.map((input) => input.displayName),
				['RESULT', 'PAYLOAD'],
			);
			assert.deepStrictEqual(outputs, ['main']);
		},
	},
	{
		name: 'node description exposes targetPath as required and resultSource as optional',
		run: () => {
			const properties = description.properties as Array<{
				name: string;
				required?: boolean;
			}>;
			assert.deepStrictEqual(
				properties.map((property) => property.name),
				['targetPath', 'resultSource', 'addToHistory', 'historyPath'],
			);
			assert.strictEqual(
				properties.find((property) => property.name === 'targetPath')?.required,
				true,
			);
			assert.notStrictEqual(
				properties.find((property) => property.name === 'resultSource')?.required,
				true,
			);
		},
	},
	{
		name: 'node description exposes Add to History as an optional boolean defaulting to false',
		run: () => {
			const properties = description.properties as Array<{
				name: string;
				type: string;
				default?: unknown;
				required?: boolean;
			}>;
			const addToHistory = properties.find((property) => property.name === 'addToHistory');

			assert.ok(addToHistory, 'addToHistory property must exist');
			assert.strictEqual(addToHistory.type, 'boolean');
			assert.strictEqual(addToHistory.default, false);
			assert.notStrictEqual(addToHistory.required, true);
		},
	},
	{
		name: 'node description defaults History Path to context.history and shows it only when enabled',
		run: () => {
			const properties = description.properties as Array<{
				name: string;
				type: string;
				default?: unknown;
				displayOptions?: { show?: Record<string, unknown[]> };
			}>;
			const historyPath = properties.find((property) => property.name === 'historyPath');

			assert.ok(historyPath, 'historyPath property must exist');
			assert.strictEqual(historyPath.type, 'string');
			assert.strictEqual(historyPath.default, 'context.history');
			assert.deepStrictEqual(historyPath.displayOptions?.show, { addToHistory: [true] });
		},
	},

	// --- Add to History -------------------------------------------------------

	{
		name: 'add-to-history off leaves behaviour identical and creates no history array',
		run: async () => {
			const { execute, setInputs } = makeExecute('', 'result.ginaNode', { addToHistory: false });
			setInputs([{ json: RESULT_A }], [{ json: MESSAGE_A }]);

			const output = (await execute())[0];

			// Byte-for-byte the pre-feature output: only the target path changed.
			assert.deepStrictEqual(output[0].json, {
				event: { type: 'greeting', id: 'e-1' },
				context: { stack: [{ node: 'start' }] },
				result: { ginaNode: { foo: 'bar', status: 'completed' } },
			});
		},
	},
	{
		name: 'add-to-history omitted entirely (pre-existing saved node) behaves as before',
		run: async () => {
			// No addToHistory in the parameter set at all: getNodeParameter falls
			// back to the description default, exactly as n8n does for a node
			// saved before the option existed.
			const { execute, setInputs } = makeExecute('', 'result.ginaNode');
			setInputs([{ json: RESULT_A }], [{ json: MESSAGE_A }]);

			const output = (await execute())[0];

			assert.deepStrictEqual(output[0].json, {
				event: { type: 'greeting', id: 'e-1' },
				context: { stack: [{ node: 'start' }] },
				result: { ginaNode: { foo: 'bar', status: 'completed' } },
			});
		},
	},
	{
		name: 'add-to-history creates context.history as an array when it does not exist',
		run: async () => {
			const { execute, setInputs } = makeExecute('status', 'result.status', {
				addToHistory: true,
			});
			setInputs([{ json: RESULT_A }], [{ json: MESSAGE_A }]);

			const output = (await execute())[0];

			assert.deepStrictEqual(output[0].json, {
				event: { type: 'greeting', id: 'e-1' },
				context: {
					stack: [{ node: 'start' }],
					history: ['completed'],
				},
				result: { status: 'completed' },
			});
		},
	},
	{
		name: 'add-to-history appends the whole RESULT item when resultSource is empty',
		run: async () => {
			const { execute, setInputs } = makeExecute('', 'result.ginaNode', {
				addToHistory: true,
			});
			setInputs([{ json: RESULT_A }], [{ json: MESSAGE_A }]);

			const output = (await execute())[0];

			assert.deepStrictEqual((output[0].json as { context: { history: unknown } }).context.history, [
				{ foo: 'bar', status: 'completed' },
			]);
		},
	},
	{
		name: 'add-to-history appends to an existing history array',
		run: async () => {
			const { execute, setInputs } = makeExecute('status', 'result.status', {
				addToHistory: true,
			});
			setInputs([{ json: RESULT_A }], [
				{
					json: {
						event: { type: 'greeting', id: 'e-1' },
						context: { stack: [{ node: 'start' }], history: ['earlier', 'entries'] },
						result: {},
					},
				},
			]);

			const output = (await execute())[0];

			assert.deepStrictEqual((output[0].json as { context: { history: unknown } }).context.history, [
				'earlier',
				'entries',
				'completed',
			]);
		},
	},
	{
		name: 'add-to-history appends in order across multiple executions',
		run: async () => {
			const first = makeExecute('value', 'result.a', { addToHistory: true });
			first.setInputs([{ json: { value: 1 } }], [{ json: MESSAGE_A }]);
			const afterA = (await first.execute())[0];

			const second = makeExecute('value', 'result.b', { addToHistory: true });
			second.setInputs([{ json: { value: 2 } }], afterA as unknown as TestItem[]);
			const afterB = (await second.execute())[0];

			const third = makeExecute('value', 'result.c', { addToHistory: true });
			third.setInputs([{ json: { value: 3 } }], afterB as unknown as TestItem[]);
			const afterC = (await third.execute())[0];

			assert.deepStrictEqual((afterC[0].json as { context: { history: unknown } }).context.history, [
				1,
				2,
				3,
			]);
			// Each execution also still accumulated its own target path.
			assert.deepStrictEqual(afterC[0].json, {
				event: { type: 'greeting', id: 'e-1' },
				context: {
					stack: [{ node: 'start' }],
					history: [1, 2, 3],
				},
				result: { a: 1, b: 2, c: 3 },
			});
		},
	},
	{
		name: 'add-to-history preserves context.stack unchanged',
		run: async () => {
			const stack = [{ node: 'start' }, { node: 'middle', depth: 2 }];
			const { execute, setInputs } = makeExecute('status', 'result.status', {
				addToHistory: true,
			});
			setInputs([{ json: RESULT_A }], [{ json: { ...MESSAGE_A, context: { stack } } }]);
			const stackBefore = snapshot(stack);

			const output = (await execute())[0];
			const context = (output[0].json as { context: Record<string, unknown> }).context;

			assert.deepStrictEqual(context.stack, [{ node: 'start' }, { node: 'middle', depth: 2 }]);
			// The stack is neither replaced nor reordered, and the caller's own
			// array object is not mutated.
			assert.strictEqual(snapshot(stack), stackBefore);
			assert.notStrictEqual(context.stack, stack);
		},
	},
	{
		name: 'add-to-history preserves event unchanged',
		run: async () => {
			const { execute, setInputs } = makeExecute('status', 'result.status', {
				addToHistory: true,
			});
			setInputs([{ json: RESULT_A }], [{ json: MESSAGE_A }]);

			const output = (await execute())[0];

			assert.deepStrictEqual((output[0].json as { event: unknown }).event, MESSAGE_A.event);
			assert.notStrictEqual(
				(output[0].json as { event: unknown }).event,
				MESSAGE_A.event,
			);
		},
	},
	{
		name: 'add-to-history preserves result accumulation semantics unchanged',
		run: async () => {
			const withHistory = makeExecute('value', 'result.copied', { addToHistory: true });
			withHistory.setInputs([{ json: { value: 42 } }], [{ json: MESSAGE_A }]);

			const withoutHistory = makeExecute('value', 'result.copied', { addToHistory: false });
			withoutHistory.setInputs([{ json: { value: 42 } }], [{ json: MESSAGE_A }]);

			const on = (await withHistory.execute())[0][0].json as {
				result: Record<string, unknown>;
				context: Record<string, unknown>;
			};
			const off = (await withoutHistory.execute())[0][0].json as {
				result: Record<string, unknown>;
			};

			// Identical result accumulation in both modes; the only difference is
			// the added history array.
			assert.deepStrictEqual(on.result, off.result);
			assert.deepStrictEqual(on.result, { copied: 42 });
			assert.deepStrictEqual(on.context.history, [42]);
		},
	},
	{
		name: 'add-to-history honours the existing resultSource selection',
		run: async () => {
			const { execute, setInputs } = makeExecute('data.total', 'result.total', {
				addToHistory: true,
			});
			setInputs(
				[{ json: { data: { total: 7, other: 'ignored' } } }],
				[{ json: MESSAGE_A }],
			);

			const output = (await execute())[0];

			assert.deepStrictEqual(output[0].json, {
				event: { type: 'greeting', id: 'e-1' },
				context: {
					stack: [{ node: 'start' }],
					history: [7],
				},
				result: { total: 7 },
			});
		},
	},
	{
		name: 'add-to-history does not alias the history entry with the target value',
		run: async () => {
			const { execute, setInputs } = makeExecute('data', 'result.copied', {
				addToHistory: true,
			});
			setInputs([{ json: { data: { inner: { n: 1 } } } }], [{ json: MESSAGE_A }]);

			const output = (await execute())[0];
			const json = output[0].json as {
				result: { copied: unknown };
				context: { history: unknown[] };
			};

			assert.deepStrictEqual(json.result.copied, { inner: { n: 1 } });
			assert.deepStrictEqual(json.context.history, [{ inner: { n: 1 } }]);
			assert.notStrictEqual(json.context.history[0], json.result.copied);
		},
	},
	{
		name: 'add-to-history appends once per paired item across multiple items',
		run: async () => {
			const { execute, setInputs } = makeExecute('value', 'result.copied', {
				addToHistory: true,
			});
			setInputs(
				[{ json: { value: 'a' } }, { json: { value: 'b' } }],
				[{ json: MESSAGE_A }, { json: MESSAGE_B }],
			);

			const output = (await execute())[0];

			assert.deepStrictEqual(
				output.map(
					(item) => (item.json as { context: { history: unknown } }).context.history,
				),
				[['a'], ['b']],
			);
		},
	},
	{
		name: 'add-to-history honours a custom History Path',
		run: async () => {
			const { execute, setInputs } = makeExecute('status', 'result.status', {
				addToHistory: true,
				historyPath: 'audit.trail',
			});
			setInputs([{ json: RESULT_A }], [{ json: MESSAGE_A }]);

			const output = (await execute())[0];

			assert.deepStrictEqual(output[0].json, {
				event: { type: 'greeting', id: 'e-1' },
				context: { stack: [{ node: 'start' }] },
				result: { status: 'completed' },
				audit: { trail: ['completed'] },
			});
		},
	},
	{
		name: 'add-to-history leaves PAYLOAD items with no RESULT item untouched',
		run: async () => {
			const { execute, setInputs } = makeExecute('value', 'result.copied', {
				addToHistory: true,
			});
			setInputs([{ json: { value: 1 } }], [{ json: MESSAGE_A }, { json: MESSAGE_B }]);

			const output = (await execute())[0];

			// No RESULT item to pair with item 1, so nothing is written AND no
			// history entry is invented.
			assert.deepStrictEqual(output[1].json, MESSAGE_B);
			assert.strictEqual(
				(output[1].json as { context: Record<string, unknown> }).context.history,
				undefined,
			);
		},
	},
	{
		name: 'add-to-history throws when History Path is empty',
		run: async () => {
			const { execute, setInputs } = makeExecute('value', 'result.copied', {
				addToHistory: true,
				historyPath: '',
			});
			setInputs([{ json: { value: 1 } }], [{ json: MESSAGE_A }]);

			await assert.rejects(execute(), /'History Path' must be a non-empty/);
		},
	},
	{
		name: 'add-to-history throws when History Path points at a non-array',
		run: async () => {
			const { execute, setInputs } = makeExecute('value', 'result.copied', {
				addToHistory: true,
			});
			setInputs([{ json: { value: 1 } }], [
				{ json: { context: { history: 'not-an-array' } } },
			]);

			await assert.rejects(execute(), /exists on PAYLOAD item 0 but is not an array/);
		},
	},
	{
		name: 'add-to-history tolerates an explicitly null history and initialises it',
		run: async () => {
			const { execute, setInputs } = makeExecute('value', 'result.copied', {
				addToHistory: true,
			});
			setInputs([{ json: { value: 1 } }], [
				{ json: { context: { history: null } } },
			]);

			const output = (await execute())[0];

			assert.deepStrictEqual(output[0].json, {
				context: { history: [1] },
				result: { copied: 1 },
			});
		},
	},
	{
		name: 'add-to-history does not let a prototype-polluting History Path pollute Object.prototype',
		run: async () => {
			const { execute, setInputs } = makeExecute('value', 'result.copied', {
				addToHistory: true,
				historyPath: '__proto__.polluted',
			});
			setInputs([{ json: { value: 1 } }], [{ json: MESSAGE_A }]);

			await execute();

			assert.strictEqual(
				(Object.prototype as unknown as Record<string, unknown>).polluted,
				undefined,
				'Object.prototype must not gain a "polluted" property',
			);
		},
	},
];

for (const t of tests) {
	test(t.name, t.run);
}
