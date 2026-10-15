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

/** The conceptual message shape the stack/history mechanics operate on. */
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
const MESSAGE_C = {
	event: { type: 'closing', id: 'e-3' },
	context: { stack: [{ node: 'start' }, { node: 'middle' }, { node: 'end' }] },
	result: {},
};
/** A payload that carries an event but has no context object at all. */
const MESSAGE_WITHOUT_CONTEXT = {
	event: { type: 'greeting', id: 'e-1' },
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
				['targetPath', 'resultSource', 'addToStack', 'stackPath', 'finalise', 'historyPath'],
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
		name: 'node description exposes Add to Stack as an optional boolean defaulting to false',
		run: () => {
			const properties = description.properties as Array<{
				name: string;
				type: string;
				default?: unknown;
				required?: boolean;
			}>;
			const addToStack = properties.find((property) => property.name === 'addToStack');

			assert.ok(addToStack, 'addToStack property must exist');
			assert.strictEqual(addToStack.type, 'boolean');
			assert.strictEqual(addToStack.default, false);
			assert.notStrictEqual(addToStack.required, true);
		},
	},
	{
		name: 'node description exposes Finalise as an optional boolean defaulting to false',
		run: () => {
			const properties = description.properties as Array<{
				name: string;
				type: string;
				default?: unknown;
				required?: boolean;
			}>;
			const finalise = properties.find((property) => property.name === 'finalise');

			assert.ok(finalise, 'finalise property must exist');
			assert.strictEqual(finalise.type, 'boolean');
			assert.strictEqual(finalise.default, false);
			assert.notStrictEqual(finalise.required, true);
		},
	},
	{
		name: 'node description defaults Stack Path to context.stack and shows it only for Add to Stack',
		run: () => {
			const properties = description.properties as Array<{
				name: string;
				type: string;
				default?: unknown;
				displayOptions?: { show?: Record<string, unknown[]> };
			}>;
			const stackPath = properties.find((property) => property.name === 'stackPath');

			assert.ok(stackPath, 'stackPath property must exist');
			assert.strictEqual(stackPath.type, 'string');
			assert.strictEqual(stackPath.default, 'context.stack');
			assert.deepStrictEqual(stackPath.displayOptions?.show, { addToStack: [true] });
		},
	},
	{
		name: 'node description defaults History Path to context.history and shows it only for Finalise',
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
			assert.deepStrictEqual(historyPath.displayOptions?.show, { finalise: [true] });
		},
	},

	// --- Optional execution-context mechanics ---------------------------------
	//
	// Add to Stack pushes the accumulated value onto a stack; Finalise closes
	// the whole stack into ONE history entry and clears the live stack. Both are
	// off by default, and the pre-existing Result accumulation is untouched by
	// either of them.

	{
		name: 'both options false leaves behaviour identical and touches neither stack nor history',
		run: async () => {
			const { execute, setInputs } = makeExecute('', 'result.ginaNode', {
				addToStack: false,
				finalise: false,
			});
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
		name: 'both options omitted (pre-existing saved node) behaves exactly as before',
		run: async () => {
			// Neither addToStack nor finalise in the parameter set at all:
			// getNodeParameter falls back to the description defaults, exactly as n8n
			// does for a node saved before these options existed.
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
		name: 'add-to-stack creates context.stack when absent',
		run: async () => {
			const { execute, setInputs } = makeExecute('status', 'result.status', {
				addToStack: true,
			});
			setInputs([{ json: RESULT_A }], [{ json: MESSAGE_WITHOUT_CONTEXT }]);

			const output = (await execute())[0];

			assert.deepStrictEqual(output[0].json, {
				event: { type: 'greeting', id: 'e-1' },
				context: { stack: ['completed'] },
				result: { status: 'completed' },
			});
		},
	},
	{
		name: 'add-to-stack creates the whole context object when absent',
		run: async () => {
			const { execute, setInputs } = makeExecute('status', 'result.status', {
				addToStack: true,
			});
			setInputs([{ json: RESULT_A }], [{ json: { event: { type: 'greeting' }, result: {} } }]);

			const output = (await execute())[0];

			assert.deepStrictEqual(output[0].json, {
				event: { type: 'greeting' },
				context: { stack: ['completed'] },
				result: { status: 'completed' },
			});
		},
	},
	{
		name: 'add-to-stack appends to an existing stack without overwriting it',
		run: async () => {
			const { execute, setInputs } = makeExecute('status', 'result.status', {
				addToStack: true,
			});
			setInputs([{ json: RESULT_A }], [{ json: MESSAGE_A }]);

			const output = (await execute())[0];

			assert.deepStrictEqual(output[0].json, {
				event: { type: 'greeting', id: 'e-1' },
				context: { stack: [{ node: 'start' }, 'completed'] },
				result: { status: 'completed' },
			});
		},
	},
	{
		name: 'add-to-stack appends the whole RESULT item when resultSource is empty',
		run: async () => {
			const { execute, setInputs } = makeExecute('', 'result.ginaNode', {
				addToStack: true,
			});
			setInputs([{ json: RESULT_A }], [{ json: MESSAGE_A }]);

			const output = (await execute())[0];

			assert.deepStrictEqual(
				(output[0].json as { context: { stack: unknown } }).context.stack,
				[{ node: 'start' }, { foo: 'bar', status: 'completed' }],
			);
		},
	},
	{
		name: 'add-to-stack preserves ordering across multiple operations',
		run: async () => {
			const first = makeExecute('value', 'result.a', { addToStack: true });
			first.setInputs([{ json: { value: 1 } }], [{ json: MESSAGE_A }]);
			const afterA = (await first.execute())[0];

			const second = makeExecute('value', 'result.b', { addToStack: true });
			second.setInputs([{ json: { value: 2 } }], afterA as unknown as TestItem[]);
			const afterB = (await second.execute())[0];

			const third = makeExecute('value', 'result.c', { addToStack: true });
			third.setInputs([{ json: { value: 3 } }], afterB as unknown as TestItem[]);
			const afterC = (await third.execute())[0];

			assert.deepStrictEqual(afterC[0].json, {
				event: { type: 'greeting', id: 'e-1' },
				context: { stack: [{ node: 'start' }, 1, 2, 3] },
				result: { a: 1, b: 2, c: 3 },
			});
		},
	},
	{
		name: 'add-to-stack preserves event unchanged',
		run: async () => {
			const { execute, setInputs } = makeExecute('status', 'result.status', {
				addToStack: true,
			});
			setInputs([{ json: RESULT_A }], [{ json: MESSAGE_A }]);

			const output = (await execute())[0];

			assert.deepStrictEqual((output[0].json as { event: unknown }).event, MESSAGE_A.event);
			assert.notStrictEqual((output[0].json as { event: unknown }).event, MESSAGE_A.event);
		},
	},
	{
		name: 'add-to-stack preserves result accumulation semantics',
		run: async () => {
			const { execute, setInputs } = makeExecute('status', 'result.status', {
				addToStack: true,
			});
			setInputs([{ json: RESULT_A }], [{ json: MESSAGE_A }]);

			const output = (await execute())[0];

			assert.deepStrictEqual((output[0].json as { result: unknown }).result, {
				status: 'completed',
			});
		},
	},
	{
		name: 'add-to-stack preserves unrelated context properties',
		run: async () => {
			const { execute, setInputs } = makeExecute('status', 'result.status', {
				addToStack: true,
			});
			setInputs([{ json: RESULT_A }], [
				{
					json: {
						event: { type: 'greeting' },
						context: { stack: [{ node: 'start' }], history: [{ stack: [] }], uow: 'u-9' },
						result: {},
					},
				},
			]);

			const output = (await execute())[0];

			assert.deepStrictEqual(output[0].json, {
				event: { type: 'greeting' },
				context: {
					stack: [{ node: 'start' }, 'completed'],
					history: [{ stack: [] }],
					uow: 'u-9',
				},
				result: { status: 'completed' },
			});
		},
	},
	{
		name: 'add-to-stack does not alias the stack entry with the RESULT or target value',
		run: async () => {
			const { execute, setInputs } = makeExecute('data', 'result.copied', {
				addToStack: true,
			});
			setInputs([{ json: { data: { inner: { n: 1 } } } }], [{ json: MESSAGE_A }]);

			const output = (await execute())[0];
			const json = output[0].json as {
				result: { copied: unknown };
				context: { stack: unknown[] };
			};

			assert.deepStrictEqual(json.result.copied, { inner: { n: 1 } });
			assert.deepStrictEqual(json.context.stack[1], { inner: { n: 1 } });
			assert.notStrictEqual(json.context.stack[1], json.result.copied);
			assert.notStrictEqual(json.context.stack[1], (json.result.copied as { inner: unknown }).inner);
		},
	},
	{
		name: 'finalise with an existing stack creates context.history',
		run: async () => {
			const { execute, setInputs } = makeExecute('status', 'result.status', {
				finalise: true,
			});
			setInputs([{ json: RESULT_A }], [
				{ json: { event: { type: 'greeting' }, context: { stack: [{ node: 'start' }] }, result: {} } },
			]);

			const output = (await execute())[0];

			assert.deepStrictEqual(output[0].json, {
				event: { type: 'greeting' },
				context: { stack: [], history: [{ stack: [{ node: 'start' }] }] },
				result: { status: 'completed' },
			});
		},
	},
	{
		name: 'finalise appends exactly ONE history entry holding the complete stack',
		run: async () => {
			const { execute, setInputs } = makeExecute('status', 'result.status', {
				finalise: true,
			});
			setInputs([{ json: RESULT_A }], [
				{ json: { context: { stack: [1, 2, 3, 4] } } },
			]);

			const output = (await execute())[0];
			const context = (output[0].json as { context: Record<string, unknown> }).context;
			const history = context.history as unknown[];

			assert.strictEqual(history.length, 1, 'one finalisation must add one history entry');
			assert.deepStrictEqual(history[0], { stack: [1, 2, 3, 4] });
		},
	},
	{
		name: 'finalise clears the live stack',
		run: async () => {
			const { execute, setInputs } = makeExecute('status', 'result.status', {
				finalise: true,
			});
			setInputs([{ json: RESULT_A }], [{ json: { context: { stack: [{ node: 'a' }] } } }]);

			const output = (await execute())[0];

			assert.deepStrictEqual((output[0].json as { context: { stack: unknown } }).context.stack, []);
		},
	},
	{
		name: 'finalise preserves event unchanged',
		run: async () => {
			const { execute, setInputs } = makeExecute('status', 'result.status', {
				finalise: true,
			});
			setInputs([{ json: RESULT_A }], [{ json: MESSAGE_A }]);

			const output = (await execute())[0];

			assert.deepStrictEqual((output[0].json as { event: unknown }).event, MESSAGE_A.event);
		},
	},
	{
		name: 'finalise preserves result accumulation semantics',
		run: async () => {
			const { execute, setInputs } = makeExecute('status', 'result.status', {
				finalise: true,
			});
			setInputs([{ json: RESULT_A }], [{ json: MESSAGE_A }]);

			const output = (await execute())[0];

			assert.deepStrictEqual((output[0].json as { result: unknown }).result, {
				status: 'completed',
			});
		},
	},
	{
		name: 'finalise history snapshot is not mutated when the stack changes afterwards',
		run: async () => {
			const first = makeExecute('value', 'result.a', { finalise: true });
			first.setInputs([{ json: { value: 'x' } }], [{ json: MESSAGE_A }]);
			const afterA = (await first.execute())[0];

			const second = makeExecute('value', 'result.b', { addToStack: true });
			second.setInputs([{ json: { value: 'y' } }], afterA as unknown as TestItem[]);
			const afterB = (await second.execute())[0];

			const context = (afterB[0].json as { context: Record<string, unknown> }).context;
			assert.deepStrictEqual(context.history, [{ stack: [{ node: 'start' }] }]);
			assert.deepStrictEqual(context.stack, ['y']);

			// The stored snapshot must not alias the live stack array or its entries.
			const snapshotEntry = (context.history as Array<{ stack: unknown[] }>)[0];
			assert.notStrictEqual(snapshotEntry.stack, context.stack);
			assert.notStrictEqual(snapshotEntry.stack[0], (context.stack as unknown[])[0]);
		},
	},
	{
		name: 'add-to-stack plus finalise pushes the current value first, then finalises it',
		run: async () => {
			const { execute, setInputs } = makeExecute('status', 'result.status', {
				addToStack: true,
				finalise: true,
			});
			setInputs([{ json: RESULT_A }], [{ json: MESSAGE_A }]);

			const output = (await execute())[0];

			assert.deepStrictEqual(output[0].json, {
				event: { type: 'greeting', id: 'e-1' },
				context: {
					stack: [],
					history: [{ stack: [{ node: 'start' }, 'completed'] }],
				},
				result: { status: 'completed' },
			});
		},
	},
	{
		name: 'add-to-stack plus finalise closes a context that had no stack yet',
		run: async () => {
			const { execute, setInputs } = makeExecute('data', 'result.copied', {
				addToStack: true,
				finalise: true,
			});
			setInputs([{ json: { data: { inner: { n: 1 } } } }], [
				{ json: { event: { type: 'greeting' }, result: {} } },
			]);

			const output = (await execute())[0];

			assert.deepStrictEqual(output[0].json, {
				event: { type: 'greeting' },
				context: { stack: [], history: [{ stack: [{ inner: { n: 1 } }] }] },
				result: { copied: { inner: { n: 1 } } },
			});
		},
	},
	{
		name: 'finalise without add-to-stack finalises the existing stack unchanged',
		run: async () => {
			const { execute, setInputs } = makeExecute('value', 'result.copied', {
				finalise: true,
			});
			setInputs([{ json: { value: 'not-pushed' } }], [
				{ json: { context: { stack: [{ node: 'start' }] } } },
			]);

			const output = (await execute())[0];
			const context = (output[0].json as { context: Record<string, unknown> }).context;

			assert.deepStrictEqual(context.history, [{ stack: [{ node: 'start' }] }]);
			assert.deepStrictEqual(context.stack, []);
		},
	},
	{
		name: 'finalise with no existing stack records an empty stack entry',
		run: async () => {
			const { execute, setInputs } = makeExecute('value', 'result.copied', {
				finalise: true,
			});
			setInputs([{ json: { value: 1 } }], [{ json: { result: {} } }]);

			const output = (await execute())[0];

			assert.deepStrictEqual(output[0].json, {
				context: { stack: [], history: [{ stack: [] }] },
				result: { copied: 1 },
			});
		},
	},
	{
		name: 'multiple finalisations produce separate history entries',
		run: async () => {
			const first = makeExecute('value', 'result.a', { addToStack: true });
			first.setInputs([{ json: { value: 'a' } }], [{ json: MESSAGE_A }]);
			const afterA = (await first.execute())[0];

			const close = makeExecute('value', 'result.b', { addToStack: true, finalise: true });
			close.setInputs([{ json: { value: 'b' } }], afterA as unknown as TestItem[]);
			const afterB = (await close.execute())[0];

			const second = makeExecute('value', 'result.c', { addToStack: true });
			second.setInputs([{ json: { value: 'c' } }], afterB as unknown as TestItem[]);
			const afterC = (await second.execute())[0];

			const closeAgain = makeExecute('value', 'result.d', { addToStack: true, finalise: true });
			closeAgain.setInputs([{ json: { value: 'd' } }], afterC as unknown as TestItem[]);
			const afterD = (await closeAgain.execute())[0];

			const context = (afterD[0].json as { context: Record<string, unknown> }).context;

			assert.deepStrictEqual(context.history, [
				{ stack: [{ node: 'start' }, 'a', 'b'] },
				{ stack: ['c', 'd'] },
			]);
			assert.deepStrictEqual(context.stack, []);
		},
	},
	{
		name: 'custom Stack Path is used for both push and finalise',
		run: async () => {
			const { execute, setInputs } = makeExecute('status', 'result.status', {
				addToStack: true,
				finalise: true,
				stackPath: 'audit.trail',
			});
			// The default context.stack is present and must be left completely alone:
			// a custom Stack Path replaces it as the path this node manages.
			setInputs([{ json: RESULT_A }], [
				{ json: { context: { stack: [{ node: 'start' }] } } },
			]);

			const output = (await execute())[0];

			assert.deepStrictEqual(output[0].json, {
				audit: { trail: [] },
				// History Path was left at its default, so the closed stack lands in
				// context.history while the untouched context.stack survives.
				context: {
					stack: [{ node: 'start' }],
					history: [{ stack: ['completed'] }],
				},
				result: { status: 'completed' },
			});
		},
	},
	{
		name: 'custom History Path receives the finalised stack',
		run: async () => {
			const { execute, setInputs } = makeExecute('status', 'result.status', {
				finalise: true,
				historyPath: 'audit.trail',
			});
			setInputs([{ json: RESULT_A }], [
				{ json: { context: { stack: [{ node: 'start' }] } } },
			]);

			const output = (await execute())[0];

			assert.deepStrictEqual(output[0].json, {
				audit: { trail: [{ stack: [{ node: 'start' }] }] },
				context: { stack: [] },
				result: { status: 'completed' },
			});
		},
	},
	{
		name: 'an existing history array is preserved and appended to',
		run: async () => {
			const { execute, setInputs } = makeExecute('status', 'result.status', {
				finalise: true,
			});
			setInputs([{ json: RESULT_A }], [
				{
					json: {
						context: {
							stack: [{ node: 'start' }],
							history: [{ stack: ['from-a-previous-run'] }],
						},
					},
				},
			]);

			const output = (await execute())[0];

			assert.deepStrictEqual(
				(output[0].json as { context: { history: unknown } }).context.history,
				[{ stack: ['from-a-previous-run'] }, { stack: [{ node: 'start' }] }],
			);
		},
	},
	{
		name: 'an explicitly null stack is initialised as an array',
		run: async () => {
			const { execute, setInputs } = makeExecute('status', 'result.status', {
				addToStack: true,
			});
			setInputs([{ json: RESULT_A }], [{ json: { context: { stack: null } } }]);

			const output = (await execute())[0];

			assert.deepStrictEqual((output[0].json as { context: { stack: unknown } }).context.stack, [
				'completed',
			]);
		},
	},
	{
		name: 'an explicitly null history is initialised as an array',
		run: async () => {
			const { execute, setInputs } = makeExecute('status', 'result.status', {
				finalise: true,
			});
			setInputs([{ json: RESULT_A }], [
				{ json: { context: { stack: [], history: null } } },
			]);

			const output = (await execute())[0];

			assert.deepStrictEqual(
				(output[0].json as { context: { history: unknown } }).context.history,
				[{ stack: [] }],
			);
		},
	},
	{
		name: 'add-to-stack throws when Stack Path is empty',
		run: async () => {
			const { execute, setInputs } = makeExecute('value', 'result.copied', {
				addToStack: true,
				stackPath: '',
			});
			setInputs([{ json: { value: 1 } }], [{ json: MESSAGE_A }]);

			await assert.rejects(execute(), /'Stack Path' must be a non-empty/);
		},
	},
	{
		name: 'finalise throws when History Path is empty',
		run: async () => {
			const { execute, setInputs } = makeExecute('value', 'result.copied', {
				finalise: true,
				historyPath: ' . . ',
			});
			setInputs([{ json: { value: 1 } }], [{ json: MESSAGE_A }]);

			await assert.rejects(execute(), /'History Path' must be a non-empty/);
		},
	},
	{
		name: 'add-to-stack throws rather than overwriting a non-array Stack Path',
		run: async () => {
			const { execute, setInputs } = makeExecute('value', 'result.copied', {
				addToStack: true,
			});
			setInputs([{ json: { value: 1 } }], [{ json: { context: { stack: 'not-an-array' } } }]);

			await assert.rejects(execute(), /'Stack Path' points at 'context.stack'/);
			await assert.rejects(execute(), /exists on PAYLOAD item 0 but is not an array/);
		},
	},
	{
		name: 'finalise throws rather than overwriting a non-array History Path',
		run: async () => {
			const { execute, setInputs } = makeExecute('value', 'result.copied', {
				finalise: true,
			});
			setInputs([{ json: { value: 1 } }], [
				{ json: { context: { stack: [], history: { not: 'an array' } } } },
			]);

			await assert.rejects(execute(), /'History Path' points at 'context.history'/);
		},
	},
	{
		name: 'finalise throws rather than overwriting a non-array Stack Path',
		run: async () => {
			const { execute, setInputs } = makeExecute('value', 'result.copied', {
				finalise: true,
			});
			setInputs([{ json: { value: 1 } }], [{ json: { context: { stack: 7 } } }]);

			await assert.rejects(execute(), /'Stack Path' points at 'context.stack'/);
		},
	},
	{
		name: 'stack and history paths keep prototype-pollution protections intact',
		run: async () => {
			const pushOnly = makeExecute('value', 'result.copied', {
				addToStack: true,
				stackPath: '__proto__.stackPolluted',
			});
			pushOnly.setInputs([{ json: { value: 1 } }], [{ json: MESSAGE_A }]);
			await pushOnly.execute();

			const finaliseOnly = makeExecute('value', 'result.copied', {
				finalise: true,
				historyPath: '__proto__.historyPolluted',
			});
			finaliseOnly.setInputs([{ json: { value: 1 } }], [{ json: MESSAGE_A }]);
			await finaliseOnly.execute();

			assert.strictEqual(
				(Object.prototype as unknown as Record<string, unknown>).stackPolluted,
				undefined,
				'Object.prototype must not gain a "stackPolluted" property',
			);
			assert.strictEqual(
				(Object.prototype as unknown as Record<string, unknown>).historyPolluted,
				undefined,
				'Object.prototype must not gain a "historyPolluted" property',
			);
		},
	},
	{
		name: 'multi-item execution appends per paired item and leaves unpaired items untouched',
		run: async () => {
			const { execute, setInputs } = makeExecute('value', 'result.copied', {
				addToStack: true,
			});
			setInputs(
				[{ json: { value: 'a' } }, { json: { value: 'b' } }],
				[{ json: MESSAGE_A }, { json: MESSAGE_B }, { json: MESSAGE_C }],
			);

			const output = (await execute())[0];

			assert.strictEqual(output.length, 3);
			assert.deepStrictEqual(
				output.map((item) => (item.json as { context: { stack: unknown } }).context.stack),
				[
					[{ node: 'start' }, 'a'],
					[{ node: 'start' }, { node: 'middle' }, 'b'],
					[{ node: 'start' }, { node: 'middle' }, { node: 'end' }],
				],
			);
			// The unpaired PAYLOAD item is passed through completely unchanged: no
			// stack append and no history entry are invented for it.
			assert.deepStrictEqual(output[2].json, MESSAGE_C);
		},
	},
	{
		name: 'multi-item execution finalises per paired item independently',
		run: async () => {
			const { execute, setInputs } = makeExecute('value', 'result.copied', {
				finalise: true,
			});
			setInputs(
				[{ json: { value: 'a' } }, { json: { value: 'b' } }],
				[
					{ json: { context: { stack: [1] } } },
					{ json: { context: { stack: [2] } } },
				],
			);

			const output = (await execute())[0];

			assert.deepStrictEqual(
				output.map((item) => (item.json as { context: Record<string, unknown> }).context),
				[{ stack: [], history: [{ stack: [1] }] }, { stack: [], history: [{ stack: [2] }] }],
			);
		},
	},
	{
		name: 'multi-item execution keeps per-item stack and history state separate',
		run: async () => {
			const { execute, setInputs } = makeExecute('value', 'result.copied', {
				addToStack: true,
			});
			setInputs(
				[{ json: { value: 'a' } }, { json: { value: 'b' } }],
				[{ json: { context: { stack: ['x'] } } }, { json: { context: { stack: ['y'] } } }],
			);

			const output = (await execute())[0];

			assert.deepStrictEqual(
				output.map((item) => (item.json as { context: { stack: unknown } }).context.stack),
				[['x', 'a'], ['y', 'b']],
			);
		},
	},
	{
		name: 'stack/history options do not disturb binary, metadata or paired item',
		run: async () => {
			const { execute, setInputs } = makeExecute('status', 'result.status', {
				addToStack: true,
				finalise: true,
			});
			setInputs(
				[{ json: RESULT_A }],
				[
					{
						json: MESSAGE_A,
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
		},
	},
	{
		name: 'stack and history options do not mutate the incoming PAYLOAD item',
		run: async () => {
			const { execute, setInputs } = makeExecute('status', 'result.status', {
				addToStack: true,
				finalise: true,
			});
			const payloadItem: TestItem = { json: JSON.parse(JSON.stringify(MESSAGE_A)) };
			const payloadBefore = snapshot(payloadItem.json);

			setInputs([{ json: RESULT_A }], [payloadItem]);
			const output = (await execute())[0];

			assert.strictEqual(snapshot(payloadItem.json), payloadBefore);
			assert.notStrictEqual(output[0].json, payloadItem.json);
			assert.notStrictEqual(
				(output[0].json as { context: { stack: unknown } }).context.stack,
				(payloadItem.json as { context: { stack: unknown } }).context.stack,
			);
		},
	},
];

for (const t of tests) {
	test(t.name, t.run);
}
