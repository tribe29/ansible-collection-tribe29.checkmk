#!/usr/bin/python
# -*- encoding: utf-8; py-indent-offset: 4 -*-

# Copyright: (c) 2022, Robin Gierse <robin.gierse@tribe29.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: discovery

short_description: Discover services in Checkmk.

# If this is part of a collection, you need to use semantic versioning,
# i.e. the version is of the form "2.5.0" and not "2.4".
version_added: "0.0.1"

description:
- Discovery services within Checkmk.

extends_documentation_fragment: [tribe29.checkmk.common]

options:
    host_name:
        description: The host who's services you want to manage.
        type: str
    state:
        description: The action to perform during discovery.
        type: str
        default: new
        choices: [new, remove, fix_all, refresh, only_host_labels]
    host_names:
        description: A list of host names for bulk discovery.
        type: list
        elements: str
        default: []
    mode:
        description: The mode of the discovery.
        type: str
        default: single
        choices: [single, bulk]
    do_full_scan:
        description:
            - Whether to perform a full scan of the host or work with cached data.
        type: bool
        default: True
    ignore_errors:
        description:
            - Whether to ignore error in single check plugins during discovery.
        type: bool
        default: True
    bulk_size:
        description: How many host to discover in one batch.
        type: int
        default: 10

author:
    - Robin Gierse (@robin-tribe29)
"""

EXAMPLES = r"""
# Create a single host.
- name: "Add newly discovered services on host."
  tribe29.checkmk.discovery:
    server_url: "http://localhost/"
    site: "my_site"
    automation_user: "automation"
    automation_secret: "$SECRET"
    host_name: "my_host"
    state: "new"
- name: "Add newly discovered services, update labels and remove vanished services on host."
  tribe29.checkmk.discovery:
    server_url: "http://localhost/"
    site: "my_site"
    automation_user: "automation"
    automation_secret: "$SECRET"
    host_name: "my_host"
    state: "fix_all"
- name: "Bulk discover several hosts."
  tribe29.checkmk.discovery:
    server_url: "http://localhost/"
    site: "my_site"
    automation_user: "automation"
    automation_secret: "$SECRET"
    mode: 'bulk'
    host_names:
      - "my_host1"
      - "my_host2"
      - "my_host3"
    state: "new"
"""

RETURN = r"""
http_code:
    description: The HTTP code the Checkmk API returns.
    type: int
    returned: always
    sample: '200'
message:
    description: The output message that the module generates.
    type: str
    returned: always
    sample: 'Host created.'
"""

import json

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.urls import fetch_url


def run_module():
    module_args = dict(
        server_url=dict(type="str", required=True),
        site=dict(type="str", required=True),
        automation_user=dict(type="str", required=True),
        automation_secret=dict(type="str", required=True, no_log=True),
        host_name=dict(type="str"),
        host_names=dict(type="list", elements="str", default=[]),
        mode=dict(
            type="str",
            default="single",
            choices=["single", "bulk"],
        ),
        do_full_scan=dict(type="bool", default=True),
        ignore_errors=dict(type="bool", default=True),
        bulk_size=dict(type="int", default=10),
        state=dict(
            type="str",
            default="new",
            choices=["new", "remove", "fix_all", "refresh", "only_host_labels"],
        ),
    )

    result = dict(changed=False, failed=False, http_code="", msg="")

    module = AnsibleModule(argument_spec=module_args, supports_check_mode=False)

    changed = False
    failed = False
    http_code = ""

    http_code_mapping = {
        # http_code: (changed, failed, "Message")
        200: (True, False, "Discovery successful."),
        400: (False, True, "Bad Request."),
        403: (False, True, "Forbidden: Configuration via WATO is disabled."),
        404: (False, True, "Not Found: Host could not be found."),
        406: (False, True, "Not Acceptable."),
        415: (False, True, "Unsupported Media Type."),
        500: (False, True, "General Server Error."),
    }

    # Declare headers including authentication to send to the Checkmk API
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": "Bearer %s %s"
        % (
            module.params.get("automation_user", ""),
            module.params.get("automation_secret", ""),
        ),
    }

    base_url = "%s/%s/check_mk/api/1.0" % (
        module.params.get("server_url", ""),
        module.params.get("site", ""),
    )

    # ToDo: Should we choose the mode based on the input of host_name and host_names?
    if module.params.get("mode") == "single":
        api_endpoint = (
            "/objects/host/"
            + module.params.get("host_name")
            + "/actions/discover_services/invoke"
        )
        params = {
           "mode": module.params.get("state", ""),
        }
    elif module.params.get("mode") == "bulk":
        api_endpoint = "/domain-types/discovery_run/actions/bulk-discovery-start/invoke"
        params = {
           "mode": module.params.get("state", ""),
           "hostnames": module.params.get("host_names", ""),
           "do_full_scan": module.params.get("do_full_scan", ""),
           "bulk_size": module.params.get("bulk_size", ""),
           "ignore_errors": module.params.get("ignore_errors", ""),
        }

    url = base_url + api_endpoint

    response, info = fetch_url(
        module, url, module.jsonify(params), headers=headers, method="POST"
    )
    http_code = info["status"]

    # Kudos to Lars G.!
    if http_code in http_code_mapping.keys():
        changed, failed, msg = http_code_mapping[http_code]
    else:
        changed, failed, msg = (
            False,
            True,
            "Error calling API. HTTP Return Code is %d" % http_code,
        )

    if failed:
        details = info.get("body", info.get("msg", "N/A"))
        msg += " Details: %s" % details

    result["msg"] = msg
    result["changed"] = changed
    result["failed"] = failed
    result["http_code"] = http_code

    if result["failed"]:
        module.fail_json(**result)

    module.exit_json(**result)


def main():
    run_module()


if __name__ == "__main__":
    main()
