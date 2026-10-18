# The infrastructure (gitea, woodpecker, registry, portainer, coredns, nginx)
# and platform (n8n, langfuse, portkey, postgres, clickhouse, ...) compose
# stacks now live in the services repository:
#
#   /home/martinp/enterprise/projects/services
#   https://github.com/mpcoaching/services  (private)
#   https://gitea.local.test/ai/services
#
# Run stack commands there:  make up | infra-up | platform-up | down | ps | logs
# (see services/makefile and services/README.md). The targets that used to live
# in this makefile (up/down/rebuild/remote-*) managed those stacks and were
# removed with the extracted directories.
