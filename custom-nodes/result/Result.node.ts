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
		// The own-property check is load-bearing, not defensive noise. A bare
		// `current[segment]` read makes an inherited key look like an existing
		// branch, so a targetPath of `__proto__.polluted` would resolve the
		// intermediate segment to Object.prototype and the final write would
		// land there. getPath and hasPath already read through hasOwnProperty;
		// this had to match, otherwise the write side stayed pollutable even
		// though the read side looked safe.
		const existing = Object.prototype.hasOwnProperty.call(current, segment)
			? current[segment]
			: undefined;
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

/**
 * Append `value` as a new last element of the array living at a dot-notation
 * path, creating the array (and any intermediate objects) when the path does
 * not exist yet.
 *
 * An existing array is appended to in place and reused, so sibling fields and
 * earlier history entries survive. The same `setSafeObjectProperty` /
 * `hasOwnProperty` discipline as `setPath` applies: a prototype-polluting
 * segment must not resolve an intermediate branch to Object.prototype.
 *
 * Returns the array that was appended to, or `undefined` when the path already
 * holds something that is not an array. The caller owns that decision because
 * only it can raise a NodeOperationError against the running node.
 */
function appendToPathArray(
	target: JsonObject,
	segments: string[],
	value: unknown,
): unknown[] | undefined {
	let current: JsonObject = target;
	for (let i = 0; i < segments.length - 1; i++) {
		const segment = segments[i];
		const existing = Object.prototype.hasOwnProperty.call(current, segment)
			? current[segment]
			: undefined;
		if (isPlainObject(existing)) {
			current = existing;
		} else {
			const created: JsonObject = {};
			setSafeObjectProperty(current, segment, created);
			current = created;
		}
	}

	const leaf = segments[segments.length - 1];
	const existing = Object.prototype.hasOwnProperty.call(current, leaf)
		? current[leaf]
		: undefined;

	if (existing !== undefined && existing !== null && !Array.isArray(existing)) {
		return undefined;
	}

	// `existing` is either a plain array (reused, so order and identity hold) or
	// nothing at all (initialised as an array).
	const array = Array.isArray(existing) ? existing : [];
	array.push(value);
	setSafeObjectProperty(current, leaf, array);
	return array;
}

export class Result implements INodeType {
	description: INodeTypeDescription = {
		displayName: 'Result',
		name: 'aiAssistantResult',
		group: ['transform'],
		version: 1,
		description:
			'Additive result accumulator. Takes the PAYLOAD input (input 2) as the base object, takes a value from the RESULT input (input 1), and writes that value into the payload at the target path. Optionally appends that same value to a history array. Emits the accumulated payload, so Result nodes can be chained. (CI deploy marker rev5)',
		defaults: {
			name: 'Result',
		},
		// Two labelled main inputs: 0 = RESULT (value source), 1 = PAYLOAD (carried
		// forward). One main output: the accumulated payload items.
		inputs: [
			{ type: NodeConnectionTypes.Main, displayName: 'RESULT' },
			{ type: NodeConnectionTypes.Main, displayName: 'PAYLOAD' },
		],
		outputs: [NodeConnectionTypes.Main],
		properties: [
			{
				displayName: 'Target Path',
				name: 'targetPath',
				type: 'string',
				default: '',
				required: true,
				description:
					'Dot-notation path in the PAYLOAD input item to write the result to, e.g. "ginaNode" or "ginaNode.result". Missing intermediate objects are created; an existing value at this path is overwritten.',
				placeholder: 'e.g. ginaNode.result',
			},
			{
				displayName: 'Result Source',
				name: 'resultSource',
				type: 'string',
				default: '',
				required: false,
				description:
					'Optional dot-notation path within the RESULT input item selecting what gets written, e.g. "status" or "data.total". Leave empty to write the entire RESULT item.',
				placeholder: 'leave empty for the whole item',
			},
			{
				displayName: 'Add to History',
				name: 'addToHistory',
				type: 'boolean',
				default: false,
				required: false,
				description:
					'When enabled, the same value written to Target Path is also appended as one new element to the array at History Path. Off by default, in which case the node behaves exactly as before.',
			},
			{
				displayName: 'History Path',
				name: 'historyPath',
				type: 'string',
				default: 'context.history',
				required: false,
				displayOptions: {
					show: {
						addToHistory: [true],
					},
				},
				description:
					'Dot-notation path of the array to append to, e.g. "context.history". Missing intermediate objects and a missing array are created. Nothing outside this path is touched, so sibling fields such as context.stack are left as they are.',
				placeholder: 'e.g. context.history',
			},
		],
	};

	async execute(this: IExecuteFunctions): Promise<INodeExecutionData[][]> {
		const resultItems = this.getInputData(RESULT_INPUT_INDEX);
		const payloadItems = this.getInputData(PAYLOAD_INPUT_INDEX);

		const resultSource = this.getNodeParameter('resultSource', 0, '') as string;
		const targetPath = this.getNodeParameter('targetPath', 0, '') as string;
		const addToHistory = this.getNodeParameter('addToHistory', 0, false) === true;
		const historyPath = this.getNodeParameter('historyPath', 0, 'context.history') as string;

		// targetPath is required: without it there is nowhere to write the result.
		const targetSegments = splitPath(targetPath);
		if (targetSegments.length === 0) {
			throw new NodeOperationError(
				this.getNode(),
				"'Target Path' must be a non-empty dot-notation path, e.g. 'ginaNode.result'.",
				{ description: 'The PAYLOAD input is the second main input of the Result node.' },
			);
		}

		// resultSource is optional. An empty (or non-string) value means "write the
		// entire RESULT item"; a supplied path means "write the value at that path".
		const sourceSegments = splitPath(resultSource);
		const writeWholeResultItem = sourceSegments.length === 0;

		// The history path is only validated when the option is on, so a node
		// that never appends keeps working with an unset History Path.
		const historySegments = addToHistory ? splitPath(historyPath) : [];
		if (addToHistory && historySegments.length === 0) {
			throw new NodeOperationError(
				this.getNode(),
				"'History Path' must be a non-empty dot-notation path when 'Add to History' is enabled, e.g. 'context.history'.",
				{ description: "Turn off 'Add to History' to skip the history append entirely." },
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
				let value: unknown;

				if (writeWholeResultItem) {
					value = resultJson;
				} else {
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
					value = getPath(resultJson, sourceSegments);
				}

				// Deep copy the value too, so the output shares no references with
				// the RESULT input item.
				setPath(json, targetSegments, copyValue(value));

				if (addToHistory) {
					// A separate copy of the value, so a later mutation of the
					// target value cannot reach back into the history entry.
					const appended = appendToPathArray(json, historySegments, copyValue(value));
					if (appended === undefined) {
						throw new NodeOperationError(
							this.getNode(),
							`'History Path' points at '${historyPath}', which exists on PAYLOAD item ${index} but is not an array.`,
							{
								description:
									"'Add to History' appends to an array. Point History Path at an array path, e.g. 'context.history'.",
								itemIndex: index,
							},
						);
					}
				}
			}

			output.push({ ...payloadItem, json: json as IDataObject });
		}

		return [output];
	}
}
