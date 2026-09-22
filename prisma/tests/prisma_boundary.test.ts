import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { prisma } from "../src/index";

function uid(): string {
  return crypto.randomUUID();
}

async function cleanup() {
  await prisma.lead.deleteMany();
  await prisma.funnelStep.deleteMany();
  await prisma.funnel.deleteMany();
}

async function createFunnel(name: string, slug: string) {
  return prisma.funnel.create({
    data: { id: uid(), name, slug },
  });
}

describe("A. Funnel creation", () => {
  beforeEach(cleanup);
  afterEach(cleanup);

  it("should create a Funnel with required fields", async () => {
    const funnel = await createFunnel("Sales Funnel", "sales-funnel");
    expect(funnel.id).toBeDefined();
    expect(funnel.name).toBe("Sales Funnel");
    expect(funnel.slug).toBe("sales-funnel");
    expect(funnel.description).toBeNull();
  });

  it("should store Funnel description when provided", async () => {
    const funnel = await prisma.funnel.create({
      data: { id: uid(), name: "Marketing", slug: "marketing", description: "Top of funnel" },
    });
    expect(funnel.description).toBe("Top of funnel");
  });
});

describe("B. FunnelStep creation", () => {
  beforeEach(cleanup);
  afterEach(cleanup);

  it("should create a FunnelStep with required fields", async () => {
    const funnel = await createFunnel("Test", "test");
    const step = await prisma.funnelStep.create({
      data: { id: uid(), name: "Awareness", order: 1, funnelId: funnel.id },
    });
    expect(step.id).toBeDefined();
    expect(step.name).toBe("Awareness");
    expect(step.order).toBe(1);
    expect(step.funnelId).toBe(funnel.id);
  });
});

describe("C. FunnelStep ordering", () => {
  beforeEach(cleanup);
  afterEach(cleanup);

  it("should support multiple ordered steps in a funnel", async () => {
    const funnel = await createFunnel("Test", "test");
    const step1 = await prisma.funnelStep.create({
      data: { id: uid(), name: "Step 1", order: 1, funnelId: funnel.id },
    });
    const step2 = await prisma.funnelStep.create({
      data: { id: uid(), name: "Step 2", order: 2, funnelId: funnel.id },
    });
    expect(step1.order).toBeLessThan(step2.order);
    const steps = await prisma.funnelStep.findMany({
      where: { funnelId: funnel.id },
      orderBy: { order: "asc" },
    });
    expect(steps).toHaveLength(2);
    expect(steps[0].order).toBe(1);
    expect(steps[1].order).toBe(2);
  });
});

describe("D. Duplicate step order within a Funnel rejected", () => {
  beforeEach(cleanup);
  afterEach(cleanup);

  it("should reject duplicate order within the same funnel", async () => {
    const funnel = await createFunnel("Test", "test");
    await prisma.funnelStep.create({
      data: { id: uid(), name: "Step A", order: 1, funnelId: funnel.id },
    });
    await expect(
      prisma.funnelStep.create({
        data: { id: uid(), name: "Step B", order: 1, funnelId: funnel.id },
      })
    ).rejects.toThrow();
  });
});

describe("E. Same step order in different Funnels succeeds", () => {
  beforeEach(cleanup);
  afterEach(cleanup);

  it("should allow same order in different funnels", async () => {
    const funnel1 = await createFunnel("Funnel 1", "funnel-1");
    const funnel2 = await createFunnel("Funnel 2", "funnel-2");
    await prisma.funnelStep.create({
      data: { id: uid(), name: "Step 1", order: 1, funnelId: funnel1.id },
    });
    const step2 = await prisma.funnelStep.create({
      data: { id: uid(), name: "Step 1", order: 1, funnelId: funnel2.id },
    });
    expect(step2.order).toBe(1);
    expect(step2.funnelId).toBe(funnel2.id);
  });
});

describe("F. Lead creation", () => {
  beforeEach(cleanup);
  afterEach(cleanup);

  it("should create a Lead with required fields", async () => {
    const lead = await prisma.lead.create({
      data: { id: uid(), email: "test@example.com" },
    });
    expect(lead.id).toBeDefined();
    expect(lead.email).toBe("test@example.com");
    expect(lead.status).toBe("new");
    expect(lead.firstName).toBeNull();
    expect(lead.funnelId).toBeNull();
  });
});

describe("G. Lead without Funnel succeeds if nullable by design", () => {
  beforeEach(cleanup);
  afterEach(cleanup);

  it("should create a Lead with null funnelId", async () => {
    const lead = await prisma.lead.create({
      data: { id: uid(), email: "orphan@example.com" },
    });
    expect(lead.funnelId).toBeNull();
  });
});

describe("H. Lead associated with Funnel succeeds", () => {
  beforeEach(cleanup);
  afterEach(cleanup);

  it("should create a Lead linked to a Funnel", async () => {
    const funnel = await createFunnel("Sales", "sales");
    const lead = await prisma.lead.create({
      data: { id: uid(), email: "lead@example.com", funnelId: funnel.id },
    });
    expect(lead.funnelId).toBe(funnel.id);
  });
});

describe("I. Funnel retrieval with steps", () => {
  beforeEach(cleanup);
  afterEach(cleanup);

  it("should retrieve a Funnel including its steps", async () => {
    const funnel = await createFunnel("Sales", "sales");
    await prisma.funnelStep.create({
      data: { id: uid(), name: "Awareness", order: 1, funnelId: funnel.id },
    });
    await prisma.funnelStep.create({
      data: { id: uid(), name: "Decision", order: 2, funnelId: funnel.id },
    });
    const found = await prisma.funnel.findUnique({
      where: { id: funnel.id },
      include: { steps: { orderBy: { order: "asc" as const } } },
    });
    expect(found).not.toBeNull();
    expect(found!.steps).toHaveLength(2);
    expect(found!.steps[0].name).toBe("Awareness");
    expect(found!.steps[1].name).toBe("Decision");
  });
});

describe("J. Funnel retrieval with leads", () => {
  beforeEach(cleanup);
  afterEach(cleanup);

  it("should retrieve a Funnel including its leads", async () => {
    const funnel = await createFunnel("Sales", "sales");
    await prisma.lead.create({ data: { id: uid(), email: "a@example.com", funnelId: funnel.id } });
    await prisma.lead.create({ data: { id: uid(), email: "b@example.com", funnelId: funnel.id } });
    const found = await prisma.funnel.findUnique({
      where: { id: funnel.id },
      include: { leads: true },
    });
    expect(found).not.toBeNull();
    expect(found!.leads).toHaveLength(2);
  });
});

describe("K. Update Funnel independently", () => {
  beforeEach(cleanup);
  afterEach(cleanup);

  it("should update Funnel description without affecting steps", async () => {
    const funnel = await createFunnel("Sales", "sales");
    await prisma.funnelStep.create({
      data: { id: uid(), name: "Step 1", order: 1, funnelId: funnel.id },
    });
    const updated = await prisma.funnel.update({
      where: { id: funnel.id },
      data: { description: "Updated description" },
    });
    expect(updated.description).toBe("Updated description");
    const steps = await prisma.funnelStep.findMany({ where: { funnelId: funnel.id } });
    expect(steps).toHaveLength(1);
  });
});

describe("L. Update FunnelStep independently", () => {
  beforeEach(cleanup);
  afterEach(cleanup);

  it("should update FunnelStep name without affecting Funnel or other steps", async () => {
    const funnel = await createFunnel("Sales", "sales");
    const step1 = await prisma.funnelStep.create({
      data: { id: uid(), name: "Old Name", order: 1, funnelId: funnel.id },
    });
    await prisma.funnelStep.create({
      data: { id: uid(), name: "Step 2", order: 2, funnelId: funnel.id },
    });
    const updated = await prisma.funnelStep.update({
      where: { id: step1.id },
      data: { name: "New Name" },
    });
    expect(updated.name).toBe("New Name");
    const funnelStill = await prisma.funnel.findUnique({ where: { id: funnel.id } });
    expect(funnelStill!.name).toBe("Sales");
  });
});

describe("M. Delete behaviour", () => {
  beforeEach(cleanup);
  afterEach(cleanup);

  it("should delete Funnel and cascade delete FunnelSteps", async () => {
    const funnel = await createFunnel("Sales", "sales");
    await prisma.funnelStep.create({
      data: { id: uid(), name: "Step 1", order: 1, funnelId: funnel.id },
    });
    await prisma.funnel.delete({ where: { id: funnel.id } });
    const steps = await prisma.funnelStep.findMany({ where: { funnelId: funnel.id } });
    expect(steps).toHaveLength(0);
  });

  it("should delete Funnel and preserve Leads by clearing their Funnel reference", async () => {
    const funnel = await createFunnel("Sales", "sales");
    const lead = await prisma.lead.create({ data: { id: uid(), email: "a@example.com", funnelId: funnel.id } });
    await prisma.funnel.delete({ where: { id: funnel.id } });
    const preserved = await prisma.lead.findUnique({ where: { id: lead.id } });
    expect(preserved).not.toBeNull();
    expect(preserved!.funnelId).toBeNull();
  });

  it("should delete Lead without affecting Funnel or other Leads", async () => {
    const funnel = await createFunnel("Sales", "sales");
    await prisma.lead.create({ data: { id: uid(), email: "a@example.com", funnelId: funnel.id } });
    const lead2 = await prisma.lead.create({
      data: { id: uid(), email: "b@example.com", funnelId: funnel.id },
    });
    await prisma.lead.delete({ where: { id: lead2.id } });
    const remaining = await prisma.lead.findMany({ where: { funnelId: funnel.id } });
    expect(remaining).toHaveLength(1);
  });
});

describe("N. Referential integrity", () => {
  beforeEach(cleanup);
  afterEach(cleanup);

  it("should reject Lead with duplicate email", async () => {
    await prisma.lead.create({ data: { id: uid(), email: "dup@example.com" } });
    await expect(
      prisma.lead.create({ data: { id: uid(), email: "dup@example.com" } })
    ).rejects.toThrow();
  });

  it("should reject Funnel with duplicate slug", async () => {
    await createFunnel("Sales", "sales");
    await expect(createFunnel("Marketing", "sales")).rejects.toThrow();
  });

  it("should reject FunnelStep whose Funnel does not exist", async () => {
    await expect(
      prisma.funnelStep.create({
        data: { id: uid(), name: "Orphan", order: 1, funnelId: uid() },
      })
    ).rejects.toThrow();
  });

  it("should reject Lead whose Funnel does not exist", async () => {
    await expect(
      prisma.lead.create({
        data: { id: uid(), email: "orphan@example.com", funnelId: uid() },
      })
    ).rejects.toThrow();
  });
});

describe("O. Generated Client schema availability", () => {
  beforeEach(cleanup);
  afterEach(cleanup);

  it("should expose all three tables through the generated Client", async () => {
    const funnelCount = await prisma.funnel.count();
    const stepCount = await prisma.funnelStep.count();
    const leadCount = await prisma.lead.count();
    expect(funnelCount).toBe(0);
    expect(stepCount).toBe(0);
    expect(leadCount).toBe(0);
  });
});

describe("P. Prisma Client connection", () => {
  afterEach(cleanup);

  it("should connect and execute a simple query", async () => {
    const result = await prisma.$executeRaw`SELECT 1 as one`;
    expect(result).toBeDefined();
  });
});