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
  return prisma.funnel.create({ data: { id: uid(), name, slug } });
}

describe("Isolation: Funnel A with steps and lead vs Funnel B", () => {
  beforeEach(cleanup);
  afterEach(cleanup);

  it("should maintain separate data between funnels", async () => {
    const funnelA = await createFunnel("Funnel A", "funnel-a");
    const funnelB = await createFunnel("Funnel B", "funnel-b");

    await prisma.funnelStep.create({ data: { id: uid(), name: "Step 1", order: 1, funnelId: funnelA.id } });
    await prisma.funnelStep.create({ data: { id: uid(), name: "Step 2", order: 2, funnelId: funnelA.id } });
    await prisma.lead.create({ data: { id: uid(), email: "lead-a@example.com", funnelId: funnelA.id } });

    await prisma.funnelStep.create({ data: { id: uid(), name: "Step 1", order: 1, funnelId: funnelB.id } });
    await prisma.funnelStep.create({ data: { id: uid(), name: "Step 2", order: 2, funnelId: funnelB.id } });
    await prisma.lead.create({ data: { id: uid(), email: "lead-b@example.com", funnelId: funnelB.id } });

    const stepsA = await prisma.funnelStep.findMany({ where: { funnelId: funnelA.id } });
    const stepsB = await prisma.funnelStep.findMany({ where: { funnelId: funnelB.id } });
    const leadsA = await prisma.lead.findMany({ where: { funnelId: funnelA.id } });
    const leadsB = await prisma.lead.findMany({ where: { funnelId: funnelB.id } });

    expect(stepsA).toHaveLength(2);
    expect(stepsB).toHaveLength(2);
    expect(leadsA).toHaveLength(1);
    expect(leadsB).toHaveLength(1);

    expect(stepsA[0].order).toBe(1);
    expect(stepsB[0].order).toBe(1);
    expect(stepsA[0].id).not.toBe(stepsB[0].id);

    const allEmails = await prisma.lead.findMany();
    const emails = allEmails.map((l) => l.email);
    expect(new Set(emails).size).toBe(emails.length);
  });

  it("should support independent updates without cross-contamination", async () => {
    const funnelA = await createFunnel("Funnel A", "funnel-a");
    const funnelB = await createFunnel("Funnel B", "funnel-b");

    const stepA = await prisma.funnelStep.create({
      data: { id: uid(), name: "A Step", order: 1, funnelId: funnelA.id },
    });
    const stepB = await prisma.funnelStep.create({
      data: { id: uid(), name: "B Step", order: 1, funnelId: funnelB.id },
    });

    await prisma.funnelStep.update({ where: { id: stepA.id }, data: { name: "Updated A" } });

    const updatedA = await prisma.funnelStep.findUnique({ where: { id: stepA.id } });
    const unchangedB = await prisma.funnelStep.findUnique({ where: { id: stepB.id } });

    expect(updatedA!.name).toBe("Updated A");
    expect(unchangedB!.name).toBe("B Step");
  });

  it("should support independent deletes without cross-contamination", async () => {
    const funnelA = await createFunnel("Funnel A", "funnel-a");
    const funnelB = await createFunnel("Funnel B", "funnel-b");

    const stepA = await prisma.funnelStep.create({
      data: { id: uid(), name: "A Step", order: 1, funnelId: funnelA.id },
    });
    const stepB = await prisma.funnelStep.create({
      data: { id: uid(), name: "B Step", order: 1, funnelId: funnelB.id },
    });

    await prisma.funnelStep.delete({ where: { id: stepA.id } });

    const remainingSteps = await prisma.funnelStep.findMany();
    expect(remainingSteps).toHaveLength(1);
    expect(remainingSteps[0].id).toBe(stepB.id);
  });
});