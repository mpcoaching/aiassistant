import {
	deepCopy,
	IDataObject,
	IExecuteFunctions,
	INodeExecutionData,
	INodeType,
	INodeTypeDescription,
	NodeConnectionTypes,
	setSafeObjectProperty,
} from 'n8n-workflow';
import { NodeOperationError } from 'n8n-workflow';

type JsonObject = Record<string, unknown>;

/** Main input that carries the RESULT items (the values to store). */
const RESULT_INPUT_INDEX = 0;
/** Main input that carries the PAYLOAD items (the objects to carry forward). */
const PAYLOAD_INPUT_INDEX = 1;

function isPlainObject(value: unknown): value is JsonObject {
	return typeof value === 'object' && value !== null && !Array.isArray(value);
}

/**
 * Deep-copy a value of unknown shape. `deepCopy` is typed for objects and
 * primitives only, so this narrows first and returns primitives as-is.
 */
function copyValue<T>(value: T): T {
	if (value === null || typeof value !== 'object') {
		return value;
	}
	return deepCopy(value as object) as T;
}

/**
 * Split a dot-notation path into its segments, e.g. `results.newResult`
 * becomes `['results', 'newResult']`. Empty segments are dropped so that
 * stray separators do not create unnamed keys.
 */
function splitPath(path: unknown): string[] {
	if (typeof path !== 'string') {
		return [];
	}
	return path
		.split('.')
		.map((segment) => segment.trim())
		.filter((segment) => segment.length > 0);
}

/**
 * Walk a dot-notation path through plain objects and report whether the full
 * path exists. A present-but-`null` value counts as present, which is why this
 * cannot be folded into a `getPath(...) !== undefined` check.
 */
function hasPath(root: JsonObject, segments: string[]): boolean {
	let current: unknown = root;
	for (const segment of segments) {
		if (!isPlainObject(current) || !Object.prototype.hasOwnProperty.call(current, segment)) {
			return false;
		}
		current = current[segment];
	}
	return true;
}

/** Resolve a dot-notation path, or `undefined` when any segment is missing. */
function getPath(root: JsonObject, segments: string[]): unknown {
	let current: unknown = root;
	for (const segment of segments) {
		if (!isPlainObject(current) || !Object.prototype.hasOwnProperty.call(current, segment)) {
			return undefined;
		}
		current = current[segment];
	}
	return current;
}

/**
 * Write `value` at a dot-notation path, creating intermediate plain objects as
 * needed and reusing existing ones so sibling fields survive. Uses
 * `setSafeObjectProperty` so prototype-polluting keys are never written.
 */
function setPath(target: JsonObject, segments: string[], value: unknown): void {
	let current: JsonObject = target;
	for (let i = 0; i < segments.length - 1; i++) {
		const segment = segments[i];
		const existing = current[segment];
		if (isPlainObject(existing)) {
			current = existing;
		} else {
			const created: JsonObject = {};
			setSafeObjectProperty(current, segment, created);
			current = created;
		}
	}
	setSafeObjectProperty(current, segments[segments.length - 1], value);
}

export class Result implements INodeType {
	description: INodeTypeDescription = {
		displayName: 'Result',
		name: 'aiAssistantResult',
		group: ['transform'],
		version: 1,
		description:
			'Additive result accumulator. Reads a value from the RESULT input (input 1) and writes it into the PAYLOAD input (input 2) at a target path, emitting the accumulated payload. Chain multiple Result nodes to accumulate results across operations. (CI deploy marker rev4)',
		defaults: {
			name: 'Result',
		},
		// Two main inputs: 0 = RESULT (value source), 1 = PAYLOAD (carried forward).
		// One main output: the accumulated payload items.
		inputs: [NodeConnectionTypes.Main, NodeConnectionTypes.Main],
		outputs: [NodeConnectionTypes.Main],
		properties: [
			{
				displayName: 'Result Source',
				name: 'resultSource',
				type: 'string',
				default: '',
				description:
					'Dot-notation path in the RESULT input item to read the value from, e.g. "value" or "data.total".',
				placeholder: 'e.g. value',
			},
			{
				displayName: 'Target Path',
				name: 'targetPath',
				type: 'string',
				default: '',
				description:
					'Dot-notation path in the PAYLOAD input item to write the value to, e.g. "results.newResult". Missing intermediate objects are created; an existing value at this path is overwritten.',
				placeholder: 'e.g. results.newResult',
			},
		],
	};

	async execute(this: IExecuteFunctions): Promise<INodeExecutionData[][]> {
		const resultItems = this.getInputData(RESULT_INPUT_INDEX);
		const payloadItems = this.getInputData(PAYLOAD_INPUT_INDEX);

		const resultSource = this.getNodeParameter('resultSource', 0, '') as string;
		const targetPath = this.getNodeParameter('targetPath', 0, '') as string;

		const sourceSegments = splitPath(resultSource);
		if (sourceSegments.length === 0) {
			throw new NodeOperationError(
				this.getNode(),
				"'Result Source' must be a non-empty dot-notation path, e.g. 'value'.",
				{ description: 'The RESULT input is the first main input of the Result node.' },
			);
		}

		const targetSegments = splitPath(targetPath);
		if (targetSegments.length === 0) {
			throw new NodeOperationError(
				this.getNode(),
				"'Target Path' must be a non-empty dot-notation path, e.g. 'results.newResult'.",
				{ description: 'The PAYLOAD input is the second main input of the Result node.' },
			);
		}

		// Inputs pair by item index. When the two inputs carry different item
		// counts, pairs up to the shorter input are accumulated, PAYLOAD items
		// without a corresponding RESULT item are passed through unchanged, and
		// surplus RESULT items are dropped. The output is always one item per
		// PAYLOAD item.
		const pairedCount = Math.min(resultItems.length, payloadItems.length);
		const output: INodeExecutionData[] = [];

		for (let index = 0; index < payloadItems.length; index++) {
			const payloadItem = payloadItems[index];
			// Deep copy so the emitted item never aliases the incoming PAYLOAD
			// item, and so writing the result cannot mutate it.
			const json = copyValue(payloadItem.json) as JsonObject;

			if (index < pairedCount) {
				const resultJson = resultItems[index].json as JsonObject;
				if (!hasPath(resultJson, sourceSegments)) {
					throw new NodeOperationError(
						this.getNode(),
						`RESULT item ${index} has no value at the configured Result Source path '${resultSource}'.`,
						{
							description: `RESULT item ${index} JSON keys: ${
								Object.keys(resultJson).join(', ') || '(none)'
							}.`,
							itemIndex: index,
						},
					);
				}
				// Deep copy the value too, so the output shares no references
				// with the RESULT input item.
				setPath(json, targetSegments, copyValue(getPath(resultJson, sourceSegments)));
			}

			output.push({ ...payloadItem, json: json as IDataObject });
		}

		return [output];
	}
}
