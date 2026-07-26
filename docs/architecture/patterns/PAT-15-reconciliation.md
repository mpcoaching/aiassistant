PAT-015: Reconciliation Pattern

This is the Kubernetes pattern that is probably the most relevant.

The idea:

Don't say:

"Run these steps."

Say:

"This is the desired state."

The system continually moves reality toward desired state.

Example:

Desired:

3 workflow workers running

Current:

2 running

System:

Create another

This is how Kubernetes works.

It is also how your future self-healing AI idea works.

The resulting architecture is becoming:
                    Desired State

                         |
                         |

                  Capability Contracts

                         |
                         |

                  Resolution Layer

          +--------------+--------------+
          |                             |

 Configuration                  Service Registry


                         |

                  Platform Runtime


                         |

                  Event Transport


                         |

                  Implementations