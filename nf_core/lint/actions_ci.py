#!/usr/bin/env python

import os
import re
import yaml


def actions_ci(self):
    """Checks that the GitHub Actions pipeline CI (Continuous Integration) workflow is valid.

    The ``.github/workflows/ci.yml`` GitHub Actions workflow runs the pipeline on a minimal test
    dataset using ``-profile test`` to check that no breaking changes have been introduced.
    Final result files are not checked, just that the pipeline exists successfully.

    This lint test checks this GitHub Actions workflow file for the following:

    * Workflow must be triggered on the following events:

      .. code-block:: yaml

         on:
             push:
             branches:
                 - dev
             pull_request:
             release:
             types: [published]

    * The minimum Nextflow version specified in the pipeline's ``nextflow.config`` matches that defined by ``nxf_ver`` in the test matrix:

      .. code-block:: yaml
         :emphasize-lines: 4

         strategy:
           matrix:
             # Nextflow versions: check pipeline minimum and current latest
             nxf_ver: ['19.10.0', '']

      .. note:: These ``matrix`` variables run the test workflow twice, varying the ``nxf_ver`` variable each time.
                This is used in the ``nextflow run`` commands to test the pipeline with both the latest available version
                of the pipeline (``''``) and the stated minimum required version.

    * The `Docker` container for the pipeline must use the correct pipeline version number:

        * Development pipelines:

          .. code-block:: bash

             docker tag nfcore/<pipeline_name>:dev nfcore/<pipeline_name>:dev

        * Released pipelines:

          .. code-block:: bash

             docker tag nfcore/<pipeline_name>:dev nfcore/<pipeline_name>:<pipeline-version>

        * Complete example for a released pipeline called *nf-core/example* with version number ``1.0.0``:

          .. code-block:: yaml
             :emphasize-lines: 3,8,9

             - name: Build new docker image
               if: env.GIT_DIFF
               run: docker build --no-cache . -t nfcore/example:1.0.0

             - name: Pull docker image
               if: ${{ !env.GIT_DIFF }}
               run: |
                 docker pull nfcore/example:dev
                 docker tag nfcore/example:dev nfcore/example:1.0.0
    """
    passed = []
    failed = []
    fn = os.path.join(self.wf_path, ".github", "workflows", "ci.yml")
    if not os.path.isfile(fn):
        return {"ignored": ["'.github/workflows/ci.yml' not found"]}

    with open(fn, "r") as fh:
        ciwf = yaml.safe_load(fh)

    # Check that the action is turned on for the correct events
    try:
        expected = {"push": {"branches": ["dev"]}, "pull_request": None, "release": {"types": ["published"]}}
        # NB: YAML dict key 'on' is evaluated to a Python dict key True
        assert ciwf[True] == expected
    except (AssertionError, KeyError, TypeError):
        failed.append("GitHub Actions CI is not triggered on expected events: `{}`".format(fn))
    else:
        passed.append("GitHub Actions CI is triggered on expected events: `{}`".format(fn))

    # Check that we're pulling the right docker image and tagging it properly
    if self.nf_config.get("process.container", ""):
        docker_notag = re.sub(r":(?:[\.\d]+|dev)$", "", self.nf_config.get("process.container", "").strip("\"'"))
        docker_withtag = self.nf_config.get("process.container", "").strip("\"'")

        # docker build
        docker_build_cmd = "docker build --no-cache . -t {}".format(docker_withtag)
        try:
            steps = ciwf["jobs"]["test"]["steps"]
            assert any([docker_build_cmd in step["run"] for step in steps if "run" in step.keys()])
        except (AssertionError, KeyError, TypeError):
            failed.append("CI is not building the correct docker image. Should be: `{}`".format(docker_build_cmd))
        else:
            passed.append("CI is building the correct docker image: `{}`".format(docker_build_cmd))

        # docker pull
        docker_pull_cmd = "docker pull {}:dev".format(docker_notag)
        try:
            steps = ciwf["jobs"]["test"]["steps"]
            assert any([docker_pull_cmd in step["run"] for step in steps if "run" in step.keys()])
        except (AssertionError, KeyError, TypeError):
            failed.append("CI is not pulling the correct docker image. Should be: `{}`".format(docker_pull_cmd))
        else:
            passed.append("CI is pulling the correct docker image: {}".format(docker_pull_cmd))

        # docker tag
        docker_tag_cmd = "docker tag {}:dev {}".format(docker_notag, docker_withtag)
        try:
            steps = ciwf["jobs"]["test"]["steps"]
            assert any([docker_tag_cmd in step["run"] for step in steps if "run" in step.keys()])
        except (AssertionError, KeyError, TypeError):
            failed.append("CI is not tagging docker image correctly. Should be: `{}`".format(docker_tag_cmd))
        else:
            passed.append("CI is tagging docker image correctly: {}".format(docker_tag_cmd))

    # Check that we are testing the minimum nextflow version
    try:
        matrix = ciwf["jobs"]["test"]["strategy"]["matrix"]["nxf_ver"]
        assert any([self.minNextflowVersion in matrix])
    except (KeyError, TypeError):
        failed.append("Continuous integration does not check minimum NF version: `{}`".format(fn))
    except AssertionError:
        failed.append("Minimum NF version different in CI and pipelines manifest: `{}`".format(fn))
    else:
        passed.append("Continuous integration checks minimum NF version: `{}`".format(fn))

    return {"passed": passed, "failed": failed}
