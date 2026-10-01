# Result node

Additive accumulator for n8n messages. It takes a value from its **RESULT**
input, writes it into the **PAYLOAD** input at a dot-notation **Target Path**,
and emits the accumulated payload, so Result nodes can be chained.

## Inputs / output

| | |
|---|---|
| Input 1 (`RESULT`) | value source |
| Input 2 (`PAYLOAD`) | object carried forward and written into |
| Output | one item per PAYLOAD item |

Items pair by index. When the two inputs carry different item counts, pairs up
to the shorter input are accumulated, PAYLOAD items without a corresponding
RESULT item pass through unchanged, and surplus RESULT items are dropped.

## Options

### Target Path (required)

Dot-notation path in the PAYLOAD item to write the result to, e.g.
`ginaNode` or `ginaNode.result`. Missing intermediate objects are created; an
existing value at this path is overwritten.

### Result Source (optional)

Dot-notation path within the RESULT item selecting what gets written, e.g.
`status` or `data.total`. Leave empty to write the entire RESULT item.

### Add to History (optional, default `false`)

When enabled, the **same value** written to Target Path is also appended as
one new element to the array at History Path. When disabled — the default —
the node behaves exactly as it did before this option existed, and a node saved
before the option existed keeps working unchanged.

### History Path (optional, default `context.history`)

Dot-notation path of the array to append to. It is a configurable path rather
than a hard-coded `context.history`, matching the existing Target Path /
Result Source convention, so the node stays free of any knowledge about the
message shape around it.

Missing intermediate objects and a missing array are created. An existing
array is appended to in place, so earlier entries survive. Nothing outside this
path is touched: sibling fields such as `context.stack`, and `event` and
`result`, are left exactly as they were.

If History Path is empty while Add to History is on, or points at something
that is not an array, the node fails with an explicit error rather than
overwriting data.

## Example

Given PAYLOAD

```json
{
  "event": { "type": "greeting" },
  "context": { "stack": [{ "node": "start" }] },
  "result": {}
}
```

RESULT `{"status": "completed"}`, `Result Source` = `status`,
`Target Path` = `result.status`, `Add to History` = `true`:

```json
{
  "event": { "type": "greeting" },
  "context": {
    "stack": [{ "node": "start" }],
    "history": ["completed"]
  },
  "result": { "status": "completed" }
}
```

Running a second Result node with `Target Path` = `result.greeting` and the
same option on appends to the same array, leaving `context.stack` untouched:

```json
"history": ["completed", "hello"]
```

With Add to History off, neither run touches `context`, and the output is the
original payload plus only the target-path write.

## Development

```bash
npm install
npm test    # runs tsc (pretest) then the node:test suite
```

The tests cover both the pre-existing accumulation behaviour and the history
option, including creation, appending, ordering across chained executions,
`context.stack` / `event` / `result` preservation, and prototype-pollution
safety of the history path.