# Skill: Design Data Model

## Purpose
Create comprehensive data models and database schemas that support the application's functional and non-functional requirements.

## Inputs
- solution-architecture
- requirements
- interface-specification

## Process

### 1. Review Requirements and Architecture
Read:
- Functional requirements (especially data-related requirements)
- Non-functional requirements (performance, scalability)
- Solution architecture document
- Interface specification
- Existing data models (if any)

### 2. Identify Entities
From requirements and architecture:
- List all data entities (nouns in requirements)
- Identify entity attributes and properties
- Determine entity relationships
- Identify inheritance hierarchies

### 3. Design Database Schema
For each entity:
- **Table name**: Follow naming conventions
- **Columns**:
  - Primary key (surrogate or natural)
  - Foreign keys
  - Required fields
  - Optional fields
  - Data types (string, integer, boolean, datetime, etc.)
  - Constraints (unique, not null, check constraints)
  - Default values
- **Indexes**:
  - Primary key index
  - Foreign key indexes
  - Query optimization indexes
  - Unique constraints
- **Constraints**:
  - Primary key constraints
  - Foreign key constraints (with ON DELETE/UPDATE actions)
  - Check constraints
  - Unique constraints

### 4. Define Relationships
For each relationship:
- **Type**: One-to-One, One-to-Many, Many-to-Many
- **Entities involved**: [Entity A] → [Entity B]
- **Cardinality**: 1:1, 1:N, N:M
- **Cascade behavior**: What happens on delete/update
- **Join table** (for many-to-many): Name and columns

### 5. Design for Performance
- **Indexing strategy**:
  - Which columns need indexes
  - Composite indexes for common queries
  - Covering indexes
- **Partitioning** (if needed):
  - Partition key
  - Partition strategy (range, hash, list)
- **Denormalization** (if justified):
  - Which tables to denormalize
  - What data to duplicate
  - Synchronization strategy

### 6. Plan Data Migration
If modifying existing schema:
- **Migration steps**:
  - Add new columns (backward compatible)
  - Migrate data
  - Remove old columns
- **Rollback plan**: How to revert if issues arise
- **Downtime requirements**: Can migration be done online?

### 7. Define Data Validation Rules
For each entity and field:
- **Format validation**: Email, phone, URL, etc.
- **Range validation**: Min/max values
- **Business rules**: Cross-field validation
- **Referential integrity**: Valid foreign key values

### 8. Document Data Model
Create `data-model.md` with:

```markdown
# Data Model

## Entity Relationship Diagram
[ERD diagram or description]

## Entities

### [Entity Name]
- **Description**: [What this entity represents]
- **Table**: [table_name]
- **Columns**:
  - `id` (PK): [type, description]
  - `field1`: [type, constraints, description]
  - `field2`: [type, constraints, description]
  - `created_at`: [type, description]
  - `updated_at`: [type, description]
- **Indexes**:
  - Primary key on `id`
  - Index on `field1` for [query pattern]
- **Relationships**:
  - Belongs to [Entity]
  - Has many [Entity]

## Relationships

### [Entity A] → [Entity B]
- **Type**: One-to-Many
- **Foreign Key**: [entity_b].[entity_a_id]
- **Cascade**: [ON DELETE/UPDATE behavior]

## Data Validation Rules
- [Entity].[field]: [validation rule]

## Migration Plan
[If modifying existing schema]

## Performance Considerations
- Indexing strategy
- Partitioning strategy
- Denormalization decisions
```

## Output
- data-model.md
- schema.sql (optional, for database creation)
- migration-plan.md (if modifying existing schema)

## Quality Criteria
- **Completeness**: All data entities are modeled
- **Normalization**: Appropriate normalization level (usually 3NF)
- **Performance**: Indexes support common query patterns
- **Integrity**: Constraints enforce data quality
- **Scalability**: Schema can scale to expected data volumes
- **Maintainability**: Schema is well-documented and follows conventions
- **Traceability**: Every table/column maps to a requirement