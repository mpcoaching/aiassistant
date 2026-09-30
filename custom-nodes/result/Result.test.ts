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

function makeExecute(resultSource: unknown, targetPath: unknown) {
	const params: Record<string, unknown> = { resultSource, targetPath };
	let resultItems: TestItem[] = [];
	let payloadItems: TestItem[] = [];
	const fakeThis = {
		getInputData(inputIndex = 0): TestItem[] {
			return inputIndex === 0 ? resultItems : payloadItems;
		},
		getNodeParameter(name: string) {
			return params[name] ?? '';
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
const inputs = description.inputs as unknown[];
const outputs = description.outputs as unknown[];

const tests: Array<{ name: string; run: () => Promise<void> | void }> = [
	{
		name: 'copies a simple value from the RESULT input into the PAYLOAD input',
		run: async () => {
			const { execute, setInputs } = makeExecute('value', 'results.newResult');
			setInputs(
				[{ json: { status: 'completed', value: 42 } }],
				[
					{
						json: {
							customer: '123',
							request: 'do something',
							results: { previousResult: 'already here' },
						},
					},
				],
			);

			const output = (await execute())[0];

			assert.strictEqual(output.length, 1);
			// The output item is the PAYLOAD item, not the RESULT item.
			assert.deepStrictEqual(output[0].json, {
				customer: '123',
				request: 'do something',
				results: {
					previousResult: 'already here',
					newResult: 42,
				},
			});
			assert.strictEqual('status' in output[0].json, false);
		},
	},
	{
		name: 'resolves a nested dot-notation resultSource',
		run: async () => {
			const { execute, setInputs } = makeExecute('data.result.value', 'results.deep.value');
			setInputs(
				[{ json: { data: { result: { value: 7, ignored: true } } } }],
				[{ json: { customer: '123' } }],
			);

			const output = (await execute())[0];

			assert.deepStrictEqual(output[0].json, {
				customer: '123',
				results: { deep: { value: 7 } },
			});
		},
	},
	{
		name: 'creates intermediate objects for a nested dot-notation targetPath',
		run: async () => {
			const { execute, setInputs } = makeExecute('value', 'a.b.c.d');
			setInputs([{ json: { value: 1 } }], [{ json: { customer: '123' } }]);

			const output = (await execute())[0];

			assert.deepStrictEqual(output[0].json, {
				customer: '123',
				a: { b: { c: { d: 1 } } },
			});
		},
	},
	{
		name: 'preserves existing top-level payload fields',
		run: async () => {
			const { execute, setInputs } = makeExecute('value', 'results.newResult');
			setInputs(
				[{ json: { value: 5 } }],
				[{ json: { customer: '123', request: 'do something', meta: { source: 'crm' } } }],
			);

			const output = (await execute())[0];

			assert.deepStrictEqual(output[0].json, {
				customer: '123',
				request: 'do something',
				meta: { source: 'crm' },
				results: { newResult: 5 },
			});
		},
	},
	{
		name: 'preserves existing results while adding a new one',
		run: async () => {
			const { execute, setInputs } = makeExecute('value', 'results.newResult');
			setInputs(
				[{ json: { value: 42 } }],
				[{ json: { customer: '123', results: { previousResult: 'already here' } } }],
			);

			const output = (await execute())[0];

			assert.deepStrictEqual(output[0].json, {
				customer: '123',
				results: { previousResult: 'already here', newResult: 42 },
			});
		},
	},
	{
		name: 'accumulates across two chained Result nodes',
		run: async () => {
			// Operation A: `{ customer: '123', results: {} }` + `{ value: 42 }`
			const first = makeExecute('value', 'results.operationA');
			first.setInputs([{ json: { value: 42 } }], [{ json: { customer: '123', results: {} } }]);
			const afterA = (await first.execute())[0];

			// Operation B receives the accumulated payload from A.
			const second = makeExecute('value', 'results.operationB');
			second.setInputs([{ json: { value: 99 } }], afterA as unknown as TestItem[]);
			const afterB = (await second.execute())[0];

			assert.deepStrictEqual(afterB[0].json, {
				customer: '123',
				results: { operationA: 42, operationB: 99 },
			});
		},
	},
	{
		name: 'updates an existing target value',
		run: async () => {
			const { execute, setInputs } = makeExecute('value', 'results.current');
			setInputs(
				[{ json: { value: 'new' } }],
				[{ json: { customer: '123', results: { current: 'old', keep: 'me' } } }],
			);

			const output = (await execute())[0];

			assert.deepStrictEqual(output[0].json, {
				customer: '123',
				results: { current: 'new', keep: 'me' },
			});
		},
	},
	{
		name: 'replaces a non-object sitting on an intermediate target path',
		run: async () => {
			const { execute, setInputs } = makeExecute('value', 'results.current.deep');
			setInputs([{ json: { value: 1 } }], [{ json: { results: 'not-an-object' } }]);

			const output = (await execute())[0];

			assert.deepStrictEqual(output[0].json, { results: { current: { deep: 1 } } });
		},
	},
	{
		name: 'does not mutate the RESULT or PAYLOAD input items',
		run: async () => {
			const { execute, setInputs } = makeExecute('value', 'results.newResult');
			const resultItem: TestItem = { json: { status: 'completed', value: 42, nested: { a: 1 } } };
			const payloadItem: TestItem = { json: { customer: '123', results: { previous: 'x' } } };
			const resultBefore = snapshot(resultItem.json);
			const payloadBefore = snapshot(payloadItem.json);

			setInputs([resultItem], [payloadItem]);
			const output = (await execute())[0];

			assert.strictEqual(snapshot(resultItem.json), resultBefore);
			assert.strictEqual(snapshot(payloadItem.json), payloadBefore);
			// The output shares no object references with either input.
			assert.notStrictEqual(output[0].json, payloadItem.json);
			assert.notStrictEqual(
				(output[0].json as { results: unknown }).results,
				(payloadItem.json as { results: unknown }).results,
			);
			assert.deepStrictEqual(output[0].json, {
				customer: '123',
				results: { previous: 'x', newResult: 42 },
			});
		},
	},
	{
		name: 'copies an object value without aliasing the RESULT item',
		run: async () => {
			const { execute, setInputs } = makeExecute('data', 'results.copied');
			const resultItem: TestItem = { json: { data: { inner: { n: 1 } } } };
			setInputs([resultItem], [{ json: { customer: '123' } }]);

			const output = (await execute())[0];
			const copied = (output[0].json as { results: { copied: { inner: unknown } } }).results.copied;

			assert.deepStrictEqual(copied, { inner: { n: 1 } });
			assert.notStrictEqual(copied, (resultItem.json.data as { inner: unknown }).inner);
		},
	},
	{
		name: 'copies primitives, arrays, null and false values from the RESULT input',
		run: async () => {
			const { execute, setInputs } = makeExecute('value', 'results.copied');
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
				output.map((item) => (item.json as { results: { copied: unknown } }).results.copied),
				['text', 0, false, null, [1, 2, 3]],
			);
		},
	},
	{
		name: 'pairs multiple items by index',
		run: async () => {
			const { execute, setInputs } = makeExecute('value', 'results.copied');
			setInputs(
				[{ json: { value: 1 } }, { json: { value: 2 } }, { json: { value: 3 } }],
				[
					{ json: { customer: 'a' } },
					{ json: { customer: 'b' } },
					{ json: { customer: 'c' } },
				],
			);

			const output = (await execute())[0];

			assert.strictEqual(output.length, 3);
			assert.deepStrictEqual(output[0].json, { customer: 'a', results: { copied: 1 } });
			assert.deepStrictEqual(output[1].json, { customer: 'b', results: { copied: 2 } });
			assert.deepStrictEqual(output[2].json, { customer: 'c', results: { copied: 3 } });
		},
	},
	{
		name: 'passes through PAYLOAD items that have no corresponding RESULT item',
		run: async () => {
			const { execute, setInputs } = makeExecute('value', 'results.copied');
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
			const { execute, setInputs } = makeExecute('value', 'results.copied');
			setInputs(
				[{ json: { value: 1 } }, { json: { value: 2 } }, { json: { value: 3 } }],
				[{ json: { customer: 'a' } }],
			);

			const output = (await execute())[0];

			assert.strictEqual(output.length, 1);
			assert.deepStrictEqual(output[0].json, { customer: 'a', results: { copied: 1 } });
		},
	},
	{
		name: 'returns no items when the PAYLOAD input is empty',
		run: async () => {
			const { execute, setInputs } = makeExecute('value', 'results.copied');
			setInputs([{ json: { value: 1 } }], []);

			const output = (await execute())[0];

			assert.deepStrictEqual(output, []);
		},
	},
	{
		name: 'returns PAYLOAD items unchanged when the RESULT input is empty',
		run: async () => {
			const { execute, setInputs } = makeExecute('value', 'results.copied');
			setInputs([], [{ json: { customer: 'a' } }]);

			const output = (await execute())[0];

			assert.strictEqual(output.length, 1);
			assert.deepStrictEqual(output[0].json, { customer: 'a' });
		},
	},
	{
		name: 'throws when resultSource is empty',
		run: async () => {
			const { execute, setInputs } = makeExecute('', 'results.copied');
			setInputs([{ json: { value: 1 } }], [{ json: { customer: 'a' } }]);

			await assert.rejects(execute(), /'Result Source' must be a non-empty/);
		},
	},
	{
		name: 'throws when the resultSource path is absent from a RESULT item',
		run: async () => {
			const { execute, setInputs } = makeExecute('missing.path', 'results.copied');
			setInputs(
				[{ json: { missing: { path: 1 } } }, { json: { other: 2 } }],
				[{ json: { customer: 'a' } }, { json: { customer: 'b' } }],
			);

			await assert.rejects(execute(), /RESULT item 1 has no value at the configured Result Source/);
		},
	},
	{
		name: 'throws when resultSource is not a string',
		run: async () => {
			const { execute, setInputs } = makeExecute(42, 'results.copied');
			setInputs([{ json: { value: 1 } }], [{ json: { customer: 'a' } }]);

			await assert.rejects(execute(), /'Result Source' must be a non-empty/);
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
		name: 'trims whitespace around dot-notation path segments',
		run: async () => {
			const { execute, setInputs } = makeExecute('  data . value ', ' results . copied ');
			setInputs([{ json: { data: { value: 3 } } }], [{ json: { customer: 'a' } }]);

			const output = (await execute())[0];

			assert.deepStrictEqual(output[0].json, { customer: 'a', results: { copied: 3 } });
		},
	},
	{
		name: 'preserves PAYLOAD binary, metadata and paired item and does not merge RESULT binary',
		run: async () => {
			const { execute, setInputs } = makeExecute('value', 'results.copied');
			setInputs(
				[{ json: { value: 1 }, binary: { resultFile: { data: 'cmVzdWx0' } } }],
				[
					{
						json: { customer: 'a' },
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
			assert.deepStrictEqual(output[0].json, { customer: 'a', results: { copied: 1 } });
		},
	},
	{
		name: 'node description exposes two main inputs and one main output',
		run: () => {
			assert.strictEqual(inputs.length, 2);
			assert.strictEqual(outputs.length, 1);
			assert.deepStrictEqual(inputs, ['main', 'main']);
			assert.deepStrictEqual(outputs, ['main']);
			assert.deepStrictEqual(
				description.properties.map((property) => property.name),
				['resultSource', 'targetPath'],
			);
		},
	},
];

for (const t of tests) {
	test(t.name, t.run);
}
