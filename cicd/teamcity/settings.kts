@file:Suppress("ALL")

import jetbrains.buildServer.configs.kotlin.*
import jetbrains.buildServer.configs.kotlin.buildFeatures.dockerSupport
import jetbrains.buildServer.configs.kotlin.triggers.vcs
import jetbrains.buildServer.configs.kotlin.vcs.GitVcsRoot

version = "2024.12"

project {
    name = "AI Assistant Platform"
    description = "Multi-tenant-ready SaaS deployment platform"

    vcsRoot(GiteaAiAssistant)

    features {
        dockerSupport {
            cleanupPushedImages = false
        }
    }

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
        text("REGISTRY_URL", "registry.local.test/aiassistant", label = "Registry")
        text("ENV", "dev", label = "Target environment")
        text("IMAGE_TAG", "%build.vcs.number%", label = "Image tag (git sha)")
        password("REGISTRY_USER", "", label = "Registry username")
        password("REGISTRY_PASSWORD", "", label = "Registry password")
    }
}

object GiteaAiAssistant : GitVcsRoot({
    name = "Gitea ai/aiassistant"
    url = "ssh://git@gitea:22/ai/aiassistant.git"
    branch = "refs/heads/main"
    authMethod = defaultPrivateKey {
        userName = "git"
    }
    pollInterval = 30
})

object AgentUnitTests : BuildType({
    name = "1. Agent Unit Tests"
    description = "pytest + vitest"

    vcs { root(GiteaAiAssistant) }

    steps {
        script {
            name = "Python units"
            scriptContent = "echo 'Python tests placeholder'"
        }
        script {
            name = "TypeScript units"
            scriptContent = "echo 'TypeScript tests placeholder'"
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
    description = "Platform tests placeholder"

    vcs { root(GiteaAiAssistant) }

    steps {
        script {
            name = "Platform tests"
            scriptContent = "echo 'Platform tests placeholder'"
        }
    }

    dependencies {
        snapshot(AgentUnitTests) {}
    }
})

object CoverageVerification : BuildType({
    name = "3. Coverage Verification"
    description = "Coverage ratchet"

    vcs { root(GiteaAiAssistant) }

    steps {
        script {
            name = "Coverage ratchet"
            scriptContent = "echo 'Coverage verification placeholder'"
        }
    }

    dependencies {
        snapshot(PlatformUnitTests) {}
    }
})

object DockerImageBuild : BuildType({
    name = "4. Docker Image Build"
    description = "Build app images"

    vcs { root(GiteaAiAssistant) }

    steps {
        script {
            name = "Build images"
            scriptContent = "echo 'Docker build placeholder'"
        }
    }

    dependencies {
        snapshot(CoverageVerification) {}
    }
})

object PushImageToRegistry : BuildType({
    name = "5. Push Image To Registry"
    description = "Push images to registry"

    vcs { root(GiteaAiAssistant) }

    steps {
        script {
            name = "Login + push"
            scriptContent = "echo 'Push placeholder'"
        }
    }

    dependencies {
        snapshot(DockerImageBuild) {}
    }
})

object DeployDevelopment : BuildType({
    name = "6. Deploy Development"
    description = "Deploy to dev"

    vcs { root(GiteaAiAssistant) }

    steps {
        script {
            name = "Deploy dev"
            scriptContent = "echo 'Deploy dev placeholder'"
        }
    }

    dependencies {
        snapshot(PushImageToRegistry) {}
    }
})

object IntegrationTests : BuildType({
    name = "7. Integration Tests"
    description = "Integration tests"

    vcs { root(GiteaAiAssistant) }

    steps {
        script {
            name = "Integration tests"
            scriptContent = "echo 'Integration tests placeholder'"
        }
    }

    dependencies {
        snapshot(DeployDevelopment) {}
    }
})

object PromotionApproval : BuildType({
    name = "8. Promotion Approval"
    description = "Manual promotion gate"

    type = Type.COMPOSITE

    steps {
        script {
            name = "Gate"
            scriptContent = "echo 'Manual promotion gate'"
        }
    }

    dependencies {
        snapshot(IntegrationTests) {}
    }
})

object DeployLive : BuildType({
    name = "9. Deploy Live"
    description = "Deploy to live"

    vcs { root(GiteaAiAssistant) }

    steps {
        script {
            name = "Deploy live"
            scriptContent = "echo 'Deploy live placeholder'"
        }
    }

    dependencies {
        snapshot(PromotionApproval) {}
    }
})

object Rollback : BuildType({
    name = "10. Rollback"
    description = "Rollback to prior tag"

    vcs { root(GiteaAiAssistant) }

    params {
        text("ROLLBACK_TAG", "", label = "Prior image tag")
    }

    steps {
        script {
            name = "Rollback live"
            scriptContent = "echo 'Rollback placeholder'"
        }
    }

    dependencies {
        snapshot(DeployLive) {}
    }
})
