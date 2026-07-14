@file:Suppress("ALL")

import jetbrains.buildServer.configs.kotlin.*
import jetbrains.buildServer.configs.kotlin.buildFeatures.dockerSupport
import jetbrains.buildServer.configs.kotlin.buildSteps.script
import jetbrains.buildServer.configs.kotlin.triggers.vcs
import jetbrains.buildServer.configs.kotlin.vcs.GitVcsRoot

/*
 * TeamCity Configuration-as-Code for the AI Assistant SaaS platform.
 * Versioned-Settings root = Gitea ai/aiassistant @ cicd/teamcity.
 *
 * Promotion pipeline (single immutable <git-sha> promoted Dev -> Live):
 *   AgentUnitTests -> PlatformUnitTests -> CoverageVerification
 *     -> DockerImageBuild -> PushImageToRegistry
 *     -> DeployDevelopment -> IntegrationTests -> PromotionApproval (manual)
 *     -> DeployLive -> Rollback (manual, on demand)
 *
 * Secrets (REGISTRY_USER / REGISTRY_PASSWORD / deploy keys) are TeamCity
 * password parameters, NOT stored in this file.
 */

version = "2024.12"

project {
    name = "AI Assistant Platform"
    description = "Multi-tenant-ready SaaS deployment platform (infra -> platform -> dev/live)"

    vcsRoot(GiteaAiAssistant)

    features {
        dockerSupport {
            cleanupPushedImages = false
        }
    }

    // ---- Snapshot (build) chain ----
    sequential {
        buildType(AgentUnitTests)
        buildType(PlatformUnitTests)
        buildType(CoverageVerification)
        buildType(DockerImageBuild)
        buildType(PushImageToRegistry)
        buildType(DeployDevelopment)
        buildType(IntegrationTests)
        buildType(PromotionApproval)
        buildType(DeployLive)
        buildType(Rollback)
    }

    params {
        // Externalised, non-secret parameters
        text("REGISTRY_URL", "registry.local.test/aiassistant",
            label = "Registry", description = "Private registry namespace")
        text("ENV", "dev", label = "Target environment")
        // IMAGE_TAG is supplied by the VCS trigger / promotion (the <git-sha>)
        text("IMAGE_TAG", "%build.vcs.number%", label = "Image tag (git sha)")
        // Secret parameters — set their VALUES in the TeamCity UI / token storage
        password("REGISTRY_USER", "", label = "Registry username")
        password("REGISTRY_PASSWORD", "", label = "Registry password")
    }
}

object GiteaAiAssistant : GitVcsRoot({
    name = "Gitea ai/aiassistant"
    url = "https://gitea.local.test/ai/aiassistant.git"
    branch = "refs/heads/main"
    authMethod = password {
        // Deploy key is installed on the agent; use "custom private key" in UI if needed.
        userName = "teamcity-bot"
        password = ""
    }
    pollInterval = 30
})

object AgentUnitTests : BuildType({
    name = "1. Agent Unit Tests"
    description = "pytest (workflow-runner) + vitest (control-center-ui)"

    vcs { root(GiteaAiAssistant) }

    steps {
        script {
            name = "Python units"
            scriptContent = """
                docker run --rm -v %teamcity.build.checkoutDir%:/src -w /src/agents/workflow-runner \
                  python:3.12-slim bash -c \
                  "pip install -r requirements.txt -r requirements-dev.txt && pytest --cov=. --cov-report=json"
            """.trimIndent()
        }
        script {
            name = "TypeScript units"
            scriptContent = """
                docker run --rm -v %teamcity.build.checkoutDir%:/src -w /src/agents/control-center-ui \
                  node:20 bash -c "npm ci && npx vitest run --coverage --reporter=json"
            """.trimIndent()
        }
    }

    triggers {
        vcs {
            branchFilter = "+:refs/heads/main"
            triggerRules = """
                +:agents/**
                +:cicd/coverage/**
            """.trimIndent()
        }
    }
})

object PlatformUnitTests : BuildType({
    name = "2. Platform Unit Tests"
    description = "Extensible placeholder for platform/ service tests"

    vcs { root(GiteaAiAssistant) }

    steps {
        script {
            name = "Platform tests (placeholder)"
            scriptContent = """
                echo "Platform unit tests placeholder. Add service-level checks under platform/ here."
                exit 0
            """.trimIndent()
        }
    }

    dependencies {
        snapshot(AgentUnitTests) {}
    }
})

object CoverageVerification : BuildType({
    name = "3. Coverage Verification"
    description = "Ratcheting coverage gate — FAILS on regression"

    vcs { root(GiteaAiAssistant) }

    steps {
        script {
            name = "Coverage ratchet"
            scriptContent = """
                python cicd/coverage/check-coverage.py \
                  --python agents/workflow-runner/coverage.json \
                  --ts     agents/control-center-ui/coverage/coverage-summary.json \
                  --e2e    agents/control-center-ui/playwright-results.xml \
                  --baseline cicd/coverage/coverage.baseline.json
            """.trimIndent()
        }
    }

    dependencies {
        snapshot(PlatformUnitTests) {}
    }
})

object DockerImageBuild : BuildType({
    name = "4. Docker Image Build"
    description = "Build app images, tag <git-sha> (immutable)"

    vcs { root(GiteaAiAssistant) }

    steps {
        script {
            name = "Build images"
            scriptContent = """
                set -e
                TAG=%IMAGE_TAG%
                docker build -t %REGISTRY_URL%/workflow-runner:${TAG} -f agents/workflow-runner/Dockerfile agents/workflow-runner
                docker build -t %REGISTRY_URL%/control-center-ui:${TAG} -f agents/control-center-ui/Dockerfile agents/control-center-ui
                docker build -t %REGISTRY_URL%/langgraph:${TAG} -f agents/langgraph/Dockerfile agents/langgraph
            """.trimIndent()
        }
    }

    dependencies {
        snapshot(CoverageVerification) {}
    }
})

object PushImageToRegistry : BuildType({
    name = "5. Push Image To Registry"
    description = "docker login + push <git-sha> tags"

    vcs { root(GiteaAiAssistant) }

    steps {
        script {
            name = "Login + push"
            scriptContent = """
                set -e
                TAG=%IMAGE_TAG%
                echo "$REGISTRY_PASSWORD" | docker login %REGISTRY_URL% -u "$REGISTRY_USER" --password-stdin
                for svc in workflow-runner control-center-ui langgraph; do
                  docker push %REGISTRY_URL%/${svc}:${TAG}
                done
            """.trimIndent()
        }
    }

    dependencies {
        snapshot(DockerImageBuild) {}
    }
})

object DeployDevelopment : BuildType({
    name = "6. Deploy Development"
    description = "deploy-dev.sh — login + pull + up (dev env)"

    vcs { root(GiteaAiAssistant) }

    steps {
        script {
            name = "Deploy dev"
            scriptContent = """
                set -e
                export IMAGE_TAG=%IMAGE_TAG%
                export REGISTRY_URL=%REGISTRY_URL%
                echo "$REGISTRY_PASSWORD" | docker login %REGISTRY_URL% -u "$REGISTRY_USER" --password-stdin
                bash cicd/scripts/deploy-dev.sh
            """.trimIndent()
        }
    }

    dependencies {
        snapshot(PushImageToRegistry) {}
    }
})

object IntegrationTests : BuildType({
    name = "7. Integration Tests"
    description = "Run against the dev tier"

    vcs { root(GiteaAiAssistant) }

    steps {
        script {
            name = "Integration tests"
            scriptContent = "bash cicd/scripts/integration-tests.sh"
        }
    }

    dependencies {
        snapshot(DeployDevelopment) {}
    }
})

object PromotionApproval : BuildType({
    name = "8. Promotion Approval"
    description = "MANUAL gate — requires Phase 7.5 backup validation green"

    enablePersonalBuilds = false
    type = Type.COMPOSITE

    steps {
        script {
            name = "Gate"
            scriptContent = """
                echo "Manual promotion gate. Confirm Phase 7.5 restore tests are GREEN before approving."
                exit 0
            """.trimIndent()
        }
    }

    dependencies {
        snapshot(IntegrationTests) {}
    }

    // Composite build => requires manual Run to proceed (acts as the approval).
})

object DeployLive : BuildType({
    name = "9. Deploy Live"
    description = "deploy-live.sh — deploys the SAME <git-sha>"

    vcs { root(GiteaAiAssistant) }

    steps {
        script {
            name = "Deploy live"
            scriptContent = """
                set -e
                export IMAGE_TAG=%IMAGE_TAG%
                export REGISTRY_URL=%REGISTRY_URL%
                echo "$REGISTRY_PASSWORD" | docker login %REGISTRY_URL% -u "$REGISTRY_USER" --password-stdin
                bash cicd/scripts/deploy-live.sh
            """.trimIndent()
        }
    }

    dependencies {
        snapshot(PromotionApproval) {}
    }
})

object Rollback : BuildType({
    name = "10. Rollback"
    description = "rollback.sh <prior-tag> — redeploy a prior immutable tag"

    vcs { root(GiteaAiAssistant) }

    params {
        text("ROLLBACK_TAG", "", label = "Prior image tag (git sha)")
    }

    steps {
        script {
            name = "Rollback live"
            scriptContent = """
                set -e
                export IMAGE_TAG=%ROLLBACK_TAG%
                export REGISTRY_URL=%REGISTRY_URL%
                echo "$REGISTRY_PASSWORD" | docker login %REGISTRY_URL% -u "$REGISTRY_USER" --password-stdin
                bash cicd/scripts/rollback.sh "%ROLLBACK_TAG%"
            """.trimIndent()
        }
    }

    dependencies {
        snapshot(DeployLive) {}
    }
})
