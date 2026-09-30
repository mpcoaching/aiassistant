"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.Result = void 0;
const n8n_workflow_1 = require("n8n-workflow");
const n8n_workflow_2 = require("n8n-workflow");
function isPlainObject(value) {
    return typeof value === 'object' && value !== null && !Array.isArray(value);
}
/**
 * Split a dot-notation path into segments, treating array indices as part of
 * the key (e.g. `a.b[0].c` -> `['a', 'b[0]', 'c']`).
 */
function splitPath(path) {
    return path.split('.').map((segment) => segment.trim()).filter((segment) => segment.length > 0);
}
/**
 * Resolve a dot-notation path against a nested object. Returns `undefined` when
 * any segment along the path is missing.
 */
function getPath(obj, path) {
    const segments = splitPath(path);
    let current = obj;
    for (const segment of segments) {
        if (!isPlainObject(current)) {
            return undefined;
        }
        if (!(segment in current)) {
            return undefined;
        }
        current = current[segment];
    }
    return current;
}
/**
 * Set a value at a dot-notation path, creating nested objects as needed.
 * Uses `setSafeObjectProperty` to avoid prototype-pollution keys.
 */
function setPath(target, path, value) {
    const segments = splitPath(path);
    if (segments.length === 0) {
        return;
    }
    let current = target;
    for (let i = 0; i < segments.length - 1; i++) {
        const segment = segments[i];
        const existing = current[segment];
        if (!isPlainObject(existing)) {
            const fresh = {};
            (0, n8n_workflow_1.setSafeObjectProperty)(current, segment, fresh);
            current = fresh;
        }
        else {
            current = existing;
        }
    }
    const last = segments[segments.length - 1];
    (0, n8n_workflow_1.setSafeObjectProperty)(current, last, value);
}
/**
 * Pure transform: copy the value at `resultSource` onto `targetPath` in a deep
 * copy of `json`. The source is never removed; the input object is never
 * mutated. Returns the original `json` unchanged when the source is missing.
 */
function transformItem(json, resultSource, targetPath) {
    const sourceSegments = splitPath(resultSource);
    if (sourceSegments.length === 0) {
        return json;
    }
    const value = getPath(json, resultSource);
    if (value === undefined) {
        // Source path does not exist: return the item unchanged.
        return json;
    }
    const cloned = (0, n8n_workflow_1.deepCopy)(json);
    setPath(cloned, targetPath, value);
    return cloned;
}
class Result {
    constructor() {
        this.description = {
            displayName: 'Result',
            name: 'aiAssistantResult',
            group: ['transform'],
            version: 1,
            description: 'Copy a value from a dot-notation path in the item JSON to a target path, preserving all other fields. (CI deploy marker rev3)',
            defaults: {
                name: 'Result',
            },
            inputs: [n8n_workflow_1.NodeConnectionTypes.Main],
            outputs: [n8n_workflow_1.NodeConnectionTypes.Main],
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            properties: [
                {
                    displayName: 'Result Source',
                    name: 'resultSource',
                    type: 'string',
                    default: '',
                    description: 'Dot-notation path in the item JSON to copy the value from. Leave empty to return the item unchanged.',
                    placeholder: 'e.g. context.someOperation',
                },
                {
                    displayName: 'Target Path',
                    name: 'targetPath',
                    type: 'string',
                    default: '',
                    description: 'Dot-notation path in the item JSON to copy the value to. Must not be empty.',
                    placeholder: 'e.g. result',
                },
            ],
        };
    }
    async execute() {
        const items = this.getInputData();
        const resultSource = this.getNodeParameter('resultSource', 0, '');
        const targetPath = this.getNodeParameter('targetPath', 0, '');
        if (typeof targetPath !== 'string' || targetPath.trim() === '') {
            throw new n8n_workflow_2.NodeOperationError(this.getNode(), 'Target Path must be a non-empty dot-notation string.');
        }
        const output = [];
        for (let i = 0; i < items.length; i++) {
            const item = items[i];
            const transformed = transformItem(item.json, resultSource, targetPath);
            output.push({
                ...item,
                json: transformed,
            });
        }
        return [output];
    }
}
exports.Result = Result;
