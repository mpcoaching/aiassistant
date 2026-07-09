## Rintime Interface

This is the important abstraction.

# Runtime Interface

Every AI Runtime must implement:

start()

stop()

send()

add()

drop()

run()

For Aider:

send()

↓

terminal.sendText()
add()

↓

terminal.sendText("/add ...")

etc.

That's all this document says.