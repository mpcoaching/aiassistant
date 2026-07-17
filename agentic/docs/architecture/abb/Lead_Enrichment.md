# Enterprise Architecture Building Block: Lead Enrichment

## Overview
The **Lead Enrichment** ABB provides the business capability to automatically enhance raw lead information with additional data, identify promising leads, and suggest strategic next steps. This capability is critical for sales and marketing operations, enabling more targeted and effective outreach.

## Capabilities
*   **Data Gathering**:
    *   Integrate with external APIs and browser sessions to gather additional data points for identified leads.
    *   Collect information such as company details, social profiles, industry, contact information, etc.
*   **Lead Analysis**:
    *   Process gathered data to identify "interesting" leads based on predefined criteria or AI models.
    *   Suggest potential next steps, such as commenting opportunities on social media, personalized nurturing strategies, or direct outreach.
*   **Data Storage**:
    *   Store enriched lead profiles for future reference and use by other systems.

## Business Value
*   **Increased Sales Efficiency**: Automates a time-consuming manual process, allowing sales teams to focus on engagement rather than data gathering.
*   **Improved Lead Quality**: Provides richer, more accurate lead data, leading to better qualification and higher conversion rates.
*   **Personalized Outreach**: Enables highly personalized and relevant communication strategies based on comprehensive lead profiles.
*   **Actionable Insights**: Delivers concrete suggestions for engagement, reducing guesswork and improving strategic decision-making.

## Data Entities (Owned)
*   **Lead Profile**: Represents an enriched record of a potential customer, including raw data, gathered external data, and system-generated insights/suggestions.

## Interactions
*   **Triggered by**: Control Center (user action, e.g., from a browser session).
*   **Integrates with**: External APIs (e.g., CRM, social media, data providers).
*   **Notifies**: Control Center (to display enriched data and suggestions), Observability Service.
*   **Publishes events**: `LeadEnriched` event to the Agent Bus.

## Realization
This ABB will be realized by the `Lead_Enrichment_Service` Solution Building Block (SBB).

---

## Relationship to Cognition Model

**First-class Capability, not a passive consumer.** Per the elevated modeling decision, Lead Enrichment is an enterprise business capability whose realization (the `Lead_Enrichment_Service` SBB) is a durable **Service** = a **Capability** (`kind=tool|skill`) in the canonical model (`ENTERPRISE-COGNITION-REFERENCE-ARCHITECTURE.md` §10). The reasoning core designs, creates, and invokes it; a "enrich lead" **workflow** is a transient **Session** that calls this Capability. See the `Service_Composition` ABB. (Previously tagged a consumer; reclassified by decision 2026-07-16.)
