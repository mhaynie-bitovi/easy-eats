# Workshop Plan

## Format Plan (3.5 hrs)

* 3 30-minute exercises (via instruqt)
* 1 30-minute break (3:00 - 3:30)
* Content/slides between

## Content Plan

* Modeled on the learning objectives of the Workflow/Worker Versioning Courses (LMS)
* Targeting intermediate/expert temporal devs
* Focus mostly on worker-versioning, but cover/review patching - it's still a critical skill with auto-upgrade behavior
* Called out areas of interest:
    * workflow replay testing
    * patching workflows with auto-upgrade behavior
    * pinned workflows (vs auto-upgrade)
    * Upgrade-on-Continue-as-New strategy ("trampolining")
    * emergency remediation techniques
    * worker controller

## Exercise Plan (via Instruqt)

Three exercises, each broken into multiple parts.

1. patching an NDE + doing a replay test
2. deploying changes with worker versioning
3. deploying on k8s with the worker controller

### Other Exercise Goals
- Continuity, changes should build on one another and keep example easy to grok and remember.
- It might be nice to sprinkle the different emergency remidiation techniques through all the exercises as a recurring topic.
- Each exercise should stand alone in it's own folder in the code repository.
- Each exercise should have a `practice` and `solution` folder. the practice one will be where they user makes their changes during the exercises. the solution is there to reference in case they want a hint. the solution is also the starting point for the subsequent exercise.

### Ideas For Changes to Make During Exercises
  - sending a notification to the customer when retrieving car
  - billing the customer at the end based on the length of their trip

## Learning Objectives

### From replay workshop description
  - deployment practices
  - worker routing
  - emergency remediation techniques

### From lms courses

#### Workflow Versioning
- Apply an appropriate Versioning strategy to modify your Workflows
  - Understand which types of changes can safely be deployed without versioning
  - Explain how to define and use versioning to support incompatible changes to a Workflow
  - Distinguish between the supported Versioning implementations
  - Implement a Versioned Workflow
- Understand how Temporal Event and Command Mapping applies to Workflow Versioning
  - Search for Workflow Versions and verify the correct Queues are being polled
  - Modify a Workflow using Patch Versioning
  - Verify correct implementations of Versioning strategies
- Download a Workflow Execution History in JSON format for use in compatibility tests
  - Demonstrate how to restart Workers and migrate Workflow Versions
  - Make changes in production and gracefully update your Executions
  - Test compatibility with past Executions and previous Versions using Workflow Replay

#### Worker Versioning
- Understand Worker Versioning Architecture and Deployment Strategies
  - Distinguish between Worker Deployments and Worker Deployment Versions in your application architecture
  - Explain the differences between rainbow, blue-green, and rolling deployment strategies and justify why Worker Versioning uses the rainbow approach for Temporal applications
  - Configure Worker Versioning parameters including enabling versioning, defining deployment names and Build IDs, and setting default versioning behaviors for your Workers
  - Configure Traffic Routing and Rollout Management
- Configure routing strategies using Current Version and Ramping Version to control how new and existing Workflows are distributed across different Worker Deployment Versions
  - Execute deployment Workflows using CLI commands to inspect current state, activate deployment versions, and monitor rollout progress through the complete Worker Versioning lifecycle
  - Handle Emergency Situations and Production Testing
- Execute emergency rollbacks by quickly removing Ramping Versions during incidents or moving your Workflow from problematic versions to safer ones
  - Execute emergency remediation procedures using the update-options CLI command to move Workflows between versions during critical incidents involving bugs, security vulnerabilities, or urgent fixes
  - Evaluate safe sunsetting procedures that account for active Workflows, query requirements, and proper timing to avoid data loss or service disruption during version retirement
  - Implement pre-deployment testing strategies using versioningOverride to pin test Workflows to pending versions while production traffic continues normally on current versions
