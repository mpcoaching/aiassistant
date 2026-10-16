ADR-013: Capability-Oriented Repository Structure

Decision:

Platform code will be organised around capabilities rather than technical layers. Each capability owns its contracts, providers, implementations, metadata, and tests. Shared patterns define behaviour but do not dictate global folder structure.