"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.Result = void 0;
const n8n_workflow_1 = require("n8n-workflow");
const n8n_workflow_2 = require("n8n-workflow");
/** Main input that carries the RESULT items (the values to store). */
const RESULT_INPUT_INDEX = 0;
/** Main input that carries the PAYLOAD items (the objects to carry forward). */
const PAYLOAD_INPUT_INDEX = 1;
function isPlainObject(value) {
    return typeof value === 'object' && value !== null && !Array.isArray(value);
}
/**
 * Deep-copy a value of unknown shape. `deepCopy` is typed for objects and
 * primitives only, so this narrows first and returns primitives as-is.
 */
function copyValue(value) {
    if (value === null || typeof value !== 'object') {
        return value;
    }
    return (0, n8n_workflow_1.deepCopy)(value);
}
/**
 * Split a dot-notation path into its segments, e.g. `results.newResult`
 * becomes `['results', 'newResult']`. Empty segments are dropped so that
 * stray separators do not create unnamed keys.
 */
function splitPath(path) {
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
function hasPath(root, segments) {
    let current = root;
    for (const segment of segments) {
        if (!isPlainObject(current) || !Object.prototype.hasOwnProperty.call(current, segment)) {
            return false;
        }
        current = current[segment];
    }
    return true;
}
/** Resolve a dot-notation path, or `undefined` when any segment is missing. */
function getPath(root, segments) {
    let current = root;
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
function setPath(target, segments, value) {
    let current = target;
    for (let i = 0; i < segments.length - 1; i++) {
        const segment = segments[i];
        const existing = current[segment];
        if (isPlainObject(existing)) {
            current = existing;
        }
        else {
            const created = {};
            (0, n8n_workflow_1.setSafeObjectProperty)(current, segment, created);
            current = created;
        }
    }
    (0, n8n_workflow_1.setSafeObjectProperty)(current, segments[segments.length - 1], value);
}
class Result {
    constructor() {
        this.description = {
            displayName: 'Result',
            name: 'aiAssistantResult',
            group: ['transform'],
            version: 1,
            description: 'Additive result accumulator. Takes the PAYLOAD input (input 2) as the base object, takes a value from the RESULT input (input 1), and writes that value into the payload at the target path. Emits the accumulated payload, so Result nodes can be chained. (CI deploy marker rev4)',
            defaults: {
                name: 'Result',
            },
            // Two labelled main inputs: 0 = RESULT (value source), 1 = PAYLOAD (carried
            // forward). One main output: the accumulated payload items.
            inputs: [
                { type: n8n_workflow_1.NodeConnectionTypes.Main, displayName: 'RESULT' },
                { type: n8n_workflow_1.NodeConnectionTypes.Main, displayName: 'PAYLOAD' },
            ],
            outputs: [n8n_workflow_1.NodeConnectionTypes.Main],
            properties: [
                {
                    displayName: 'Target Path',
                    name: 'targetPath',
                    type: 'string',
                    default: '',
                    required: true,
                    description: 'Dot-notation path in the PAYLOAD input item to write the result to, e.g. "ginaNode" or "ginaNode.result". Missing intermediate objects are created; an existing value at this path is overwritten.',
                    placeholder: 'e.g. ginaNode.result',
                },
                {
                    displayName: 'Result Source',
                    name: 'resultSource',
                    type: 'string',
                    default: '',
                    required: false,
                    description: 'Optional dot-notation path within the RESULT input item selecting what gets written, e.g. "status" or "data.total". Leave empty to write the entire RESULT item.',
                    placeholder: 'leave empty for the whole item',
                },
            ],
        };
    }
    async execute() {
        const resultItems = this.getInputData(RESULT_INPUT_INDEX);
        const payloadItems = this.getInputData(PAYLOAD_INPUT_INDEX);
        const resultSource = this.getNodeParameter('resultSource', 0, '');
        const targetPath = this.getNodeParameter('targetPath', 0, '');
        // targetPath is required: without it there is nowhere to write the result.
        const targetSegments = splitPath(targetPath);
        if (targetSegments.length === 0) {
            throw new n8n_workflow_2.NodeOperationError(this.getNode(), "'Target Path' must be a non-empty dot-notation path, e.g. 'ginaNode.result'.", { description: 'The PAYLOAD input is the second main input of the Result node.' });
        }
        // resultSource is optional. An empty (or non-string) value means "write the
        // entire RESULT item"; a supplied path means "write the value at that path".
        const sourceSegments = splitPath(resultSource);
        const writeWholeResultItem = sourceSegments.length === 0;
        // Inputs pair by item index. When the two inputs carry different item
        // counts, pairs up to the shorter input are accumulated, PAYLOAD items
        // without a corresponding RESULT item are passed through unchanged, and
        // surplus RESULT items are dropped. The output is always one item per
        // PAYLOAD item.
        const pairedCount = Math.min(resultItems.length, payloadItems.length);
        const output = [];
        for (let index = 0; index < payloadItems.length; index++) {
            const payloadItem = payloadItems[index];
            // Deep copy so the emitted item never aliases the incoming PAYLOAD
            // item, and so writing the result cannot mutate it.
            const json = copyValue(payloadItem.json);
            if (index < pairedCount) {
                const resultJson = resultItems[index].json;
                let value;
                if (writeWholeResultItem) {
                    value = resultJson;
                }
                else {
                    if (!hasPath(resultJson, sourceSegments)) {
                        throw new n8n_workflow_2.NodeOperationError(this.getNode(), `RESULT item ${index} has no value at the configured Result Source path '${resultSource}'.`, {
                            description: `RESULT item ${index} JSON keys: ${Object.keys(resultJson).join(', ') || '(none)'}.`,
                            itemIndex: index,
                        });
                    }
                    value = getPath(resultJson, sourceSegments);
                }
                // Deep copy the value too, so the output shares no references with
                // the RESULT input item.
                setPath(json, targetSegments, copyValue(value));
            }
            output.push({ ...payloadItem, json: json });
        }
        return [output];
    }
}
exports.Result = Result;
