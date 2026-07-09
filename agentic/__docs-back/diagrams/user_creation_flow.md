sequenceDiagram
    participant Client
    participant Gateway
    participant UserService
    participant EventBus
    
    Client->>Gateway: POST /users
    Gateway->>UserService: Create User
    UserService->>UserService: Validate & Persist
    UserService->>EventBus: Publish UserCreated
    EventBus-->>LoggingService: Notify
    UserService-->>Gateway: 201 Created