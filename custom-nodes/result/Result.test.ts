import assert from 'node:assert';
import test from 'node:test';
// eslint-disable-next-line @typescript-eslint/no-var-requires
const { Result } = require('./Result.node.js') as { Result: { new (): { description: { inputs: unknown[]; outputs: unknown[]; properties: Array<{ name: string }> }; execute: (this: unknown) => Promise<unknown[][]> } } };

function makeExecute(resultSource: string, targetPath: string) {
	const params: Record<string, string> = { resultSource, targetPath };
	let currentItems: unknown[] = [];
	const fakeThis = {
		getInputData() {
			return currentItems;
		},
		getNodeParameter(name: string) {
			return params[name] ?? '';
		},
		getNode() {
			return { name: 'Result' };
		},
	};
	return {
		execute: Result.prototype.execute.bind(fakeThis),
		setItems(items: unknown[]) {
			currentItems = items;
		},
	};
}

const tests: Array<{ name: string; run: () => Promise<void> | void }> = [
	{
		name: 'copies nested source to target while preserving all other fields',
		run: () => {
			const { execute, setItems } = makeExecute('context.someOperation', 'result');
			setItems([
				{
					json: {
						event: 'order.created',
						payload: { customerId: 'cust_1' },
						context: { someOperation: { status: 'ok', value: 42 } },
					},
				},
			]);
			return execute().then((result: unknown) => {
				const items = (result as unknown[][])[0];
				assert.strictEqual(items.length, 1);
				assert.deepStrictEqual((items[0] as { json: unknown }).json, {
					event: 'order.created',
					payload: { customerId: 'cust_1' },
					context: { someOperation: { status: 'ok', value: 42 } },
					result: { status: 'ok', value: 42 },
				});
			});
		},
	},
	{
		name: 'does not mutate the incoming item',
		run: () => {
			const { execute, setItems } = makeExecute('a', 'b');
			const inputJson = { a: 1 };
			setItems([{ json: inputJson }]);
			return execute().then((result: unknown) => {
				const items = (result as unknown[][])[0];
				assert.deepStrictEqual(inputJson, { a: 1 });
				assert.deepStrictEqual((items[0] as { json: unknown }).json, { a: 1, b: 1 });
			});
		},
	},
	{
		name: 'does not remove the source field',
		run: () => {
			const { execute, setItems } = makeExecute('a', 'b');
			setItems([{ json: { a: 1, c: 3 } }]);
			return execute().then((result: unknown) => {
				const items = (result as unknown[][])[0];
				assert.deepStrictEqual((items[0] as { json: unknown }).json, { a: 1, b: 1, c: 3 });
			});
		},
	},
	{
		name: 'updates an existing leaf at the target path',
		run: () => {
			const { execute, setItems } = makeExecute('a', 'result');
			setItems([{ json: { a: 1, result: 'old' } }]);
			return execute().then((result: unknown) => {
				const items = (result as unknown[][])[0];
				assert.deepStrictEqual((items[0] as { json: unknown }).json, { a: 1, result: 1 });
			});
		},
	},
	{
		name: 'supports nested dot-notation target paths',
		run: () => {
			const { execute, setItems } = makeExecute('a', 'out.deep.value');
			setItems([{ json: { a: 5 } }]);
			return execute().then((result: unknown) => {
				const items = (result as unknown[][])[0];
				assert.deepStrictEqual((items[0] as { json: unknown }).json, {
					a: 5,
					out: { deep: { value: 5 } },
				});
			});
		},
	},
	{
		name: 'returns the item unchanged when the source path is missing',
		run: () => {
			const { execute, setItems } = makeExecute('missing.path', 'result');
			setItems([{ json: { a: 1 } }]);
			return execute().then((result: unknown) => {
				const items = (result as unknown[][])[0];
				assert.deepStrictEqual((items[0] as { json: unknown }).json, { a: 1 });
			});
		},
	},
	{
		name: 'returns the item unchanged when resultSource is empty',
		run: () => {
			const { execute, setItems } = makeExecute('', 'result');
			setItems([{ json: { a: 1 } }]);
			return execute().then((result: unknown) => {
				const items = (result as unknown[][])[0];
				assert.deepStrictEqual((items[0] as { json: unknown }).json, { a: 1 });
			});
		},
	},
	{
		name: 'throws NodeOperationError when targetPath is empty',
		run: async () => {
			const { execute, setItems } = makeExecute('a', '');
			setItems([{ json: { a: 1 } }]);
			await assert.rejects(execute(), (err: Error) => {
				assert.ok(err instanceof Error);
				assert.match(err.message, /Target Path must be a non-empty/);
				return true;
			});
		},
	},
	{
		name: 'preserves binary and metadata on the output item',
		run: () => {
			const { execute, setItems } = makeExecute('a', 'b');
			setItems([
				{
					json: { a: 1 },
					binary: { file: { data: 'base64==' } },
					metadata: { subExecution: { id: 'x' } },
				},
			]);
			return execute().then((result: unknown) => {
				const items = (result as unknown[][])[0];
				const item = items[0] as { binary: unknown; metadata: unknown };
				assert.deepStrictEqual(item.binary, { file: { data: 'base64==' } });
				assert.deepStrictEqual(item.metadata, { subExecution: { id: 'x' } });
			});
		},
	},
	{
		name: 'produces 1:1 output for multiple input items',
		run: () => {
			const { execute, setItems } = makeExecute('v', 'copy');
			setItems([{ json: { v: 1 } }, { json: { v: 2 } }]);
			return execute().then((result: unknown) => {
				const items = (result as unknown[][])[0];
				assert.strictEqual(items.length, 2);
				assert.deepStrictEqual((items[0] as { json: unknown }).json, { v: 1, copy: 1 });
				assert.deepStrictEqual((items[1] as { json: unknown }).json, { v: 2, copy: 2 });
			});
		},
	},
	{
		name: 'copies primitive values, not just objects',
		run: () => {
			const { execute, setItems } = makeExecute('a', 'b');
			setItems([{ json: { a: 'hello' } }]);
			return execute().then((result: unknown) => {
				const items = (result as unknown[][])[0];
				assert.strictEqual((items[0] as { json: { b: unknown } }).json.b, 'hello');
			});
		},
	},
	{
		name: 'node description exposes one main input and one main output',
		run: () => {
			const node = new Result();
			assert.strictEqual(node.description.inputs.length, 1);
			assert.strictEqual(node.description.outputs.length, 1);
		},
	},
];

for (const t of tests) {
	test(t.name, t.run);
}