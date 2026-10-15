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
 * Resolve, creating as needed, the plain object that holds the FINAL segment of
 * a dot-notation path. Missing intermediate objects are created and existing
 * plain ones are reused so sibling fields survive; anything else sitting on an
 * intermediate segment is replaced by a fresh object.
 *
 * Uses `setSafeObjectProperty` so prototype-polluting keys are never written.
 * The own-property check is load-bearing, not defensive noise. A bare
 * `current[segment]` read makes an inherited key look like an existing branch,
 * so a path of `__proto__.polluted` would resolve the intermediate segment to
 * Object.prototype and the write would land there. getPath and hasPath already
 * read through hasOwnProperty; this has to match, otherwise the write side
 * stayed pollutable even though the read side looked safe.
 */
function resolveParentObject(target, segments) {
    let current = target;
    for (let i = 0; i < segments.length - 1; i++) {
        const segment = segments[i];
        const existing = Object.prototype.hasOwnProperty.call(current, segment)
            ? current[segment]
            : undefined;
        if (isPlainObject(existing)) {
            current = existing;
        }
        else {
            const created = {};
            (0, n8n_workflow_1.setSafeObjectProperty)(current, segment, created);
            current = created;
        }
    }
    return current;
}
/**
 * Write `value` at a dot-notation path, creating intermediate plain objects as
 * needed and reusing existing ones so sibling fields survive.
 */
function setPath(target, segments, value) {
    const parent = resolveParentObject(target, segments);
    (0, n8n_workflow_1.setSafeObjectProperty)(parent, segments[segments.length - 1], value);
}
/**
 * Report whether a dot-notation path holds an array, holds nothing (or an
 * explicit `null`, which is treated as "not initialised yet"), or holds
 * something else entirely.
 *
 * This deliberately reads through hasPath/getPath rather than creating anything
 * on the way: inspecting a path must not have write side effects. Use setPath
 * to materialise the array once the caller has decided to create it.
 */
function inspectPathArray(target, segments) {
    if (!hasPath(target, segments)) {
        return { kind: 'absent' };
    }
    const existing = getPath(target, segments);
    if (existing === null) {
        return { kind: 'absent' };
    }
    if (Array.isArray(existing)) {
        return { kind: 'array', array: existing };
    }
    return { kind: 'invalid' };
}
class Result {
    constructor() {
        this.description = {
            displayName: 'Result',
            name: 'aiAssistantResult',
            group: ['transform'],
            version: 1,
            description: 'Additive result accumulator. Takes the PAYLOAD input (input 2) as the base object, takes a value from the RESULT input (input 1), and writes that value into the payload at the target path. Optionally appends that value to an execution-context stack, and optionally closes that stack into a history entry. Emits the accumulated payload, so Result nodes can be chained. (CI deploy marker rev6)',
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
                {
                    displayName: 'Add to Stack',
                    name: 'addToStack',
                    type: 'boolean',
                    default: false,
                    required: false,
                    description: 'When enabled, the same value written to Target Path is appended to the array at Stack Path. The existing stack is kept and the new value becomes its last element. Off by default, in which case the stack is left alone.',
                },
                {
                    displayName: 'Stack Path',
                    name: 'stackPath',
                    type: 'string',
                    default: 'context.stack',
                    required: false,
                    displayOptions: {
                        show: {
                            addToStack: [true],
                        },
                    },
                    description: 'Dot-notation path of the array to append to, e.g. "context.stack". Missing intermediate objects and a missing array are created. Nothing outside this path is touched.',
                    placeholder: 'e.g. context.stack',
                },
                {
                    displayName: 'Finalise',
                    name: 'finalise',
                    type: 'boolean',
                    default: false,
                    required: false,
                    description: 'When enabled, takes the complete stack at Stack Path, appends ONE history entry containing a copy of it to the array at History Path, and then clears the live stack. Use it on the last node of a context to close it out.',
                },
                {
                    displayName: 'History Path',
                    name: 'historyPath',
                    type: 'string',
                    default: 'context.history',
                    required: false,
                    displayOptions: {
                        show: {
                            finalise: [true],
                        },
                    },
                    description: 'Dot-notation path of the array that closed stacks are appended to, e.g. "context.history". Missing intermediate objects and a missing array are created. Each finalisation adds one entry of the shape { stack: [...] } holding an independent copy of the stack, so later stack changes cannot alter past entries.',
                    placeholder: 'e.g. context.history',
                },
            ],
        };
    }
    async execute() {
        const resultItems = this.getInputData(RESULT_INPUT_INDEX);
        const payloadItems = this.getInputData(PAYLOAD_INPUT_INDEX);
        const resultSource = this.getNodeParameter('resultSource', 0, '');
        const targetPath = this.getNodeParameter('targetPath', 0, '');
        const addToStack = this.getNodeParameter('addToStack', 0, false) === true;
        const finalise = this.getNodeParameter('finalise', 0, false) === true;
        // Both paths are read even when only one option is on: Finalise reads and
        // then clears the stack, so it needs a stack path of its own, and the
        // defaults keep a node that only enabled one option working without
        // having to configure the other one's path.
        const stackPath = this.getNodeParameter('stackPath', 0, 'context.stack');
        const historyPath = this.getNodeParameter('historyPath', 0, 'context.history');
        // targetPath is required: without it there is nowhere to write the result.
        const targetSegments = splitPath(targetPath);
        if (targetSegments.length === 0) {
            throw new n8n_workflow_2.NodeOperationError(this.getNode(), "'Target Path' must be a non-empty dot-notation path, e.g. 'ginaNode.result'.", { description: 'The PAYLOAD input is the second main input of the Result node.' });
        }
        // resultSource is optional. An empty (or non-string) value means "write the
        // entire RESULT item"; a supplied path means "write the value at that path".
        const sourceSegments = splitPath(resultSource);
        const writeWholeResultItem = sourceSegments.length === 0;
        // Stack and history paths are only validated when the option that uses them is
        // on, so a node that never touches either keeps working with them unset.
        const stackSegments = splitPath(stackPath);
        if (addToStack && stackSegments.length === 0) {
            throw new n8n_workflow_2.NodeOperationError(this.getNode(), "'Stack Path' must be a non-empty dot-notation path when 'Add to Stack' is enabled, e.g. 'context.stack'.", { description: "Turn off 'Add to Stack' to skip the stack append entirely." });
        }
        const historySegments = splitPath(historyPath);
        if (finalise && historySegments.length === 0) {
            throw new n8n_workflow_2.NodeOperationError(this.getNode(), "'History Path' must be a non-empty dot-notation path when 'Finalise' is enabled, e.g. 'context.history'.", { description: "Turn off 'Finalise' to skip the finalisation entirely." });
        }
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
                // Order matters when both options are on: this node contributes its
                // own value to the stack first, and Finalise then closes the stack
                // that includes it. That is what lets a final Result node push its
                // own value and close the context in a single execution.
                if (addToStack) {
                    const stackState = inspectPathArray(json, stackSegments);
                    if (stackState.kind === 'invalid') {
                        throw new n8n_workflow_2.NodeOperationError(this.getNode(), `'Stack Path' points at '${stackPath}', which exists on PAYLOAD item ${index} but is not an array.`, {
                            description: "'Add to Stack' appends to an array. Point Stack Path at an array path, e.g. 'context.stack'.",
                            itemIndex: index,
                        });
                    }
                    if (stackState.kind === 'array') {
                        // Appended in place so the existing stack, its order, and any
                        // sibling fields on the same parent object all survive.
                        stackState.array.push(copyValue(value));
                    }
                    else {
                        // The path does not hold an array yet: create the array and the
                        // intermediate objects the path needs.
                        setPath(json, stackSegments, [copyValue(value)]);
                    }
                }
                if (finalise) {
                    // Snapshot the complete stack BEFORE clearing it. Each element is
                    // deep copied so the history entry is a snapshot: mutating the live
                    // stack afterwards must never reach back into past history.
                    const stackState = inspectPathArray(json, stackSegments);
                    if (stackState.kind === 'invalid') {
                        throw new n8n_workflow_2.NodeOperationError(this.getNode(), `'Stack Path' points at '${stackPath}', which exists on PAYLOAD item ${index} but is not an array.`, {
                            description: "'Finalise' reads the stack before clearing it. Point Stack Path at an array path, e.g. 'context.stack'.",
                            itemIndex: index,
                        });
                    }
                    const stackBeforeFinalise = stackState.kind === 'array' ? stackState.array : [];
                    const snapshot = stackBeforeFinalise.map((entry) => copyValue(entry));
                    const historyState = inspectPathArray(json, historySegments);
                    if (historyState.kind === 'invalid') {
                        throw new n8n_workflow_2.NodeOperationError(this.getNode(), `'History Path' points at '${historyPath}', which exists on PAYLOAD item ${index} but is not an array.`, {
                            description: "'Finalise' appends one entry per finalisation. Point History Path at an array path, e.g. 'context.history'.",
                            itemIndex: index,
                        });
                    }
                    // One entry per finalisation, holding the complete stack. Never one
                    // entry per stack element.
                    const historyEntry = { stack: snapshot };
                    if (historyState.kind === 'array') {
                        historyState.array.push(historyEntry);
                    }
                    else {
                        setPath(json, historySegments, [historyEntry]);
                    }
                    // Clear the live stack last, after the snapshot has been taken and
                    // the history entry is stored. A fresh array replaces the old one,
                    // which is what keeps the snapshot independent of the cleared stack.
                    //
                    // Stack Path and History Path are expected to be sibling arrays under
                    // the same context object (the default context.stack / context.history).
                    // A configuration that nests one inside the other is contradictory
                    // and is the user's to avoid; it is not special-cased here.
                    setPath(json, stackSegments, []);
                }
            }
            output.push({ ...payloadItem, json: json });
        }
        return [output];
    }
}
exports.Result = Result;
