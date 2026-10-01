# Result node

Additive accumulator for n8n messages. It takes a value from its **RESULT**
input, writes it into the **PAYLOAD** input at a dot-notation **Target Path**,
and emits the accumulated payload, so Result nodes can be chained.

It can additionally maintain an execution-context stack and close that stack
into a history array. The node stays generic: it knows only about accumulated
values and the optional stack/history mechanics, never about event types,
handlers, dispatchers or business domains.

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

### Add to Stack (optional, default `false`)

Appends the same value written to Target Path to the array at Stack Path. The
existing stack is kept and the new value becomes its last element. The array is
created when it does not exist.

### Stack Path (optional, default `context.stack`)

Dot-notation path of the stack array. Shown only when Add to Stack is enabled.

### Finalise (optional, default `false`)

Takes the complete stack at Stack Path, appends **one** history entry
containing a copy of it to the array at History Path, and then clears the live
stack. Use it on the last node of a context to close that context out.

### History Path (optional, default `context.history`)

Dot-notation path of the array that closed stacks are appended to. Shown only
when Finalise is enabled.

## Behaviour when both options are on

1. The normal Result accumulation runs.
2. The current accumulated value is appended to the stack.
3. That resulting stack, including the value just added, is finalised into one
   history entry.
4. The live stack is cleared.

That ordering lets a final Result node contribute its own value and close the
context in a single execution.

When only Finalise is enabled, the existing stack is finalised without adding
a new value. When only Add to Stack is enabled, the value is pushed and the
stack is left intact.

## Safety

- Stack and history paths are configurable dot-notation paths rather than
  hard-coded locations, matching the existing Target Path / Result Source
  convention.
- Both paths are validated as non-empty when their option is enabled.
- A non-array value sitting at either path raises an explicit error; it is
  never silently overwritten. An explicit `null` counts as "not initialised
  yet" and is initialised as an array.
- History entries hold an independent deep copy of the stack, so later stack
  changes cannot alter past entries, and no two entries or stack elements alias
  each other.
- Prototype-polluting path segments are never written, matching the existing
  write path.
- Nothing outside the configured stack and history paths is touched: `event`,
  `result` and all unrelated properties are left exactly as they were.

## Example

Starting PAYLOAD:

```json
{
  "event": { "event_type": "lead_generation.start" },
  "context": { "stack": [{ "event": { "event_type": "lead_generation.start" } }], "history": [] },
  "result": { "foo": "bar" }
}
```

RESULT item `{ "something": "new" }`, with `Result Source` left empty so the
whole item is used.

**Add to Stack = true** appends that item to the stack:

```json
"context": {
  "stack": [
    { "event": { "event_type": "lead_generation.start" } },
    { "something": "new" }
  ],
  "history": []
}
```

**Add to Stack = true, Finalise = true** pushes first, then closes that stack
into a single history entry and clears it:

```json
"context": {
  "stack": [],
  "history": [
    {
      "stack": [
        { "event": { "event_type": "lead_generation.start" } },
        { "something": "new" }
      ]
    }
  ]
}
```

`event`, `result` and everything else are unchanged throughout. With both
options off, neither `context.stack` nor `context.history` is touched at all.

A node that finalises twice records two separate history entries:

```json
"history": [
  { "stack": [{ "event": { "event_type": "lead_generation.start" } }, "a"] },
  { "stack": ["b"] }
]
```

## Development

```bash
npm install
npm test    # runs tsc (pretest) then the node:test suite
```

The tests cover the pre-existing accumulation behaviour and both optional
mechanics: creation, appending, ordering across chained executions, snapshot
independence, `event` / `result` / unrelated-property preservation, custom
paths, multi-item pairing, explicit errors, and prototype-pollution safety.