
import re
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)


def make_result(status, cause, fix, evidence):
    return {
        "build_status": status,
        "cause": cause,
        "fix": fix,
        "suggested_fix": fix,
        "evidence": evidence[:8]
    }


def analyze_error(logs):
    lines = logs.splitlines()
    text = logs.lower()

    # 1. Check the final Jenkins build status first.
    jenkins_status = re.findall(
        r"^\s*Finished:\s*(SUCCESS|FAILURE|ABORTED|UNSTABLE)\s*$",
        logs,
        re.IGNORECASE | re.MULTILINE
    )

    if jenkins_status:
        final_status = jenkins_status[-1].upper()

        if final_status == "SUCCESS":
            return make_result(
                "SUCCESS",
                "Jenkins reports that the build completed successfully.",
                "No build failure was reported by the final Jenkins status. "
                "Review the stage results and test reports if you want to "
                "verify the quality of the build.",
                [f"Finished: {final_status}"]
            )

        if final_status == "ABORTED":
            return make_result(
                "ABORTED",
                "The Jenkins build was aborted before normal completion.",
                "Check the Jenkins build page to determine whether a user, "
                "timeout, or pipeline condition stopped the build.",
                [f"Finished: {final_status}"]
            )

        if final_status == "UNSTABLE":
            return make_result(
                "UNSTABLE",
                "Jenkins marked the build as unstable. This often means "
                "a test or another configured quality check did not pass.",
                "Open the failed or unstable stages and inspect the test "
                "reports and configured quality checks.",
                [f"Finished: {final_status}"]
            )

    # 2. Detect specific error signatures.
    patterns = [
        (
            r"ModuleNotFoundError: No module named ['\"]?([^'\"\n]+)",
            "Python cannot import a required module.",
            "Install the missing package in the Python environment used by "
            "Jenkins. Check requirements.txt and the active virtual environment."
        ),
        (
            r"ImportError:",
            "Python failed to import a module or a required name.",
            "Read the complete ImportError message. Check the module name, "
            "installed package version, and import statement."
        ),
        (
            r"SyntaxError:|IndentationError:",
            "Python reported a syntax or indentation error.",
            "Open the Python file and line identified in the traceback. "
            "Correct the syntax or indentation and rerun the build."
        ),
        (
            r"Could not find or load main class|ClassNotFoundException",
            "Java could not locate the required class.",
            "Check the class name, package structure, compiled output, "
            "and Java classpath."
        ),
        (
            r"cannot find symbol|';' expected|illegal start of",
            "The Java compiler reported a source-code error.",
            "Inspect the compiler's file and line reference. Check names, "
            "imports, syntax, and required dependencies."
        ),
        (
            r"COMPILATION ERROR|compilation failed",
            "The compilation stage failed.",
            "Inspect the compiler messages immediately around this line "
            "to find the specific source-code error."
        ),
        (
            r"npm ERR!|npm error",
            "An npm command failed. The exact reason depends on the npm error details.",
            "Read the nearby npm error code and message. Check package.json, "
            "the working directory, dependencies, and network access as relevant."
        ),
        (
            r"ENOENT.*package\.json|package\.json.*ENOENT",
            "npm could not find package.json at the expected path.",
            "Check that package.json exists in the repository and that Jenkins "
            "runs npm from the correct directory."
        ),
        (
            r"permission denied|access is denied",
            "A required file or operation was denied permission.",
            "Check the file permissions and whether the Jenkins service account "
            "can access the required file or directory."
        ),
        (
            r"could not resolve host|UnknownHostException|name or service not known",
            "The build encountered a hostname or DNS resolution error.",
            "Verify the hostname, DNS configuration, network connection, "
            "and availability of the remote service."
        ),
        (
            r"connection refused|connect timed out|read timed out",
            "A connection to a required service failed or timed out.",
            "Check the service address and port, whether the service is running, "
            "and any relevant firewall or network restrictions."
        ),
        (
            r"AssertionError|There are test failures|Tests run:.*Failures: [1-9]",
            "One or more automated tests failed.",
            "Inspect the failing test name, assertion message, and test report. "
            "Correct the underlying issue and rerun the tests."
        ),
        (
            r"No such file or directory|FileNotFoundError|The system cannot find the path specified",
            "A required file or directory could not be found.",
            "Check the path, filename, working directory, repository checkout, "
            "and the output of earlier pipeline stages."
        ),
        (
            r"Could not read from remote repository|Authentication failed|Repository not found",
            "Git could not access the remote repository.",
            "Verify the repository URL, branch, credentials, and access permissions."
        ),
        (
            r"No space left on device|not enough space on the disk",
            "The build environment has insufficient disk space.",
            "Check available disk space and safely remove unnecessary temporary "
            "files or old build artifacts."
        ),
        (
            r"OutOfMemoryError|Java heap space|MemoryError",
            "A process ran out of available memory.",
            "Inspect memory usage and the process requirements. Adjust memory "
            "settings only after confirming sufficient system memory is available."
        ),
        (
            r"Could not find a valid Docker environment|Cannot connect to the Docker daemon",
            "The build could not access the required Docker environment.",
            "Check that Docker is installed and running, and that the Jenkins "
            "agent has permission to access the Docker daemon."
        ),
        (
            r"Waiting for agent to connect|There are no nodes with the label",
            "Jenkins could not find or connect to a suitable build agent.",
            "Check agent availability, connection status, and the labels required "
            "by the pipeline."
        ),
        (
            r"Failed to deploy|deployment failed",
            "The deployment step reported a failure.",
            "Inspect the deployment tool's detailed output to identify the "
            "specific deployment error before changing configuration."
        )
    ]

    for pattern, cause, fix in patterns:
        matches = [
            line.strip()
            for line in lines
            if re.search(pattern, line, re.IGNORECASE)
        ]

        if matches:
            # Ignore a success message that appears in an unrelated earlier stage.
            return make_result(
                "FAILURE",
                cause,
                fix,
                matches
            )

    # 3. Check explicit failed-build markers.
    failure_markers = [
        r"^\s*Finished:\s*FAILURE\s*$",
        r"^\s*BUILD FAILURE\s*$",
        r"^\s*FAILURE:\s*Build failed",
        r"^\s*ERROR: script returned exit code [1-9]\d*\s*$",
        r"^\s*script returned exit code [1-9]\d*\s*$"
    ]

    failure_lines = [
        line.strip()
        for line in lines
        if any(
            re.search(pattern, line, re.IGNORECASE)
            for pattern in failure_markers
        )
    ]

    if failure_lines:
        return make_result(
            "FAILURE",
            "The build reports a failure, but the supplied log does not "
            "contain a specific recognized root-cause message.",
            "Open the failed Jenkins stage and inspect the lines immediately "
            "before the failure marker. Identify the command that failed "
            "before changing code or configuration.",
            failure_lines
        )

    # 4. Unknown logs: do not invent a cause.
    error_lines = [
        line.strip()
        for line in lines
        if re.search(
            r"\b(error|exception|fatal|traceback|failed)\b",
            line,
            re.IGNORECASE
        )
        and not re.search(
            r"finished:\s*(success|failure|aborted|unstable)",
            line,
            re.IGNORECASE
        )
    ]

    if error_lines:
        return make_result(
            "UNKNOWN",
            "The log contains error-related messages, but no specific "
            "supported root cause could be identified.",
            "Review the evidence lines and the surrounding output from the "
            "same stage. Provide the complete error and the command that failed.",
            error_lines
        )

    return make_result(
        "UNKNOWN",
        "The root cause and final build status could not be determined "
        "from the supplied log.",
        "Paste the complete Jenkins console output, including the final "
        "build status and the lines surrounding any failed command.",
        []
    )


@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "message": "Welcome to BuildMind Backend",
        "status": "running"
    })


@app.route("/analyze", methods=["POST"])
def analyze():
    data = request.get_json(silent=True) or {}
    logs = data.get("logs", "")

    if not isinstance(logs, str) or not logs.strip():
        return jsonify({
            "error": "Please provide build logs for analysis."
        }), 400

    if len(logs) > 100000:
        return jsonify({
            "error": "Logs are too large. Please provide a smaller excerpt."
        }), 413

    result = analyze_error(logs)

    return jsonify({
        "status": "success",
        "mode": "demo",
        **result
    })


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
