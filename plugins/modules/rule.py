#!/usr/bin/python
# -*- encoding: utf-8; py-indent-offset: 4 -*-

# Copyright: (c) 2022, diademiemi <emilia@diademiemi.me> & Robin Gierse <robin.gierse@tribe29.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: rule

short_description: Manage rules in Checkmk.

# If this is part of a collection, you need to use semantic versioning,
# i.e. the version is of the form "2.5.0" and not "2.4".
version_added: "0.6.0"

description:
- Manage rules within Checkmk.

extends_documentation_fragment: [tribe29.checkmk.common]

options:
    rule:
        description: Definition of the rule as returned by the Checkmk API. When not given, the module will get all existing rules in the ruleset.
        required: false
        type: dict
    ruleset:
        description: Name of the ruleset to manage.
        type: str
        required: true
    state:
        description: State of the rule.
        choices: [present, absent]
        default: present
        type: str


author:
    - Robin Gierse (@robin-tribe29)
    - Lars Getwan (@lgetwan)
    - diademiemi (@diademiemi)
"""

EXAMPLES = r"""
# Create a rule in checkgroup_parameters:memory_percentage_used.
- name: "Create a rule in checkgroup_parameters:memory_percentage_used."
  tribe29.checkmk.rule:
    server_url: "http://localhost/"
    site: "my_site"
    automation_user: "automation"
    automation_secret: "$SECRET"
    ruleset: "checkgroup_parameters:memory_percentage_used"
    rule:
        conditions: {
            "host_labels": [],
            "host_name": {
                "match_on": [
                    "server3"
                ],
                "operator": "one_of"
            },
            "host_tags": [],
            "service_labels": []
        }
        properties: {
            "comment": "Warning at 80%\nCritical at 90%\n",
            "description": "Allow higher memory usage",
            "disabled": false,
            "documentation_url": "https://github.com/tribe29/ansible-collection-tribe29.checkmk/blob/main/plugins/modules/rules.py"
        }
        value_raw: "{'levels': [80.0, 90.0]}"
    state: "present"

# List rules in ruleset.
- name: "List rules in ruleset."
  tribe29.checkmk.rule:
    server_url: "http://localhost/"
    site: "my_site"
    automation_user: "automation"
    automation_secret: "$SECRET"
    ruleset: "checkgroup_parameters:memory_percentage_used"
  register: rules

# Import first rule from this ruleset on a different site.
- name: "Import a rule on a different site."
  tribe29.checkmk.rule:
    server_url: "http://localhost/"
    site: "my_other_site"
    automation_user: "automation"
    automation_secret: "$SECRET"
    ruleset: "checkgroup_parameters:memory_percentage_used"
    rule: "{{ rules.response.value[0].extensions }}"
    state: "present"

# Delete first rule in this ruleset.
- name: "Delete a rule."
  tribe29.checkmk.rule:
    server_url: "http://localhost/"
    site: "my_site"
    automation_user: "automation"
    automation_secret: "$SECRET"
    ruleset: "checkgroup_parameters:memory_percentage_used"
    rule: "{{ rules.response.value[0].extensions }}"
    state: "absent"
"""

RETURN = r"""
msg:
    description: The output message that the module generates. Contains the API response details in case of an error.
    type: str
    returned: always
    sample: 'Rule created.'
response:
    description: API response the module may generate, such as rule exports.
    type: dict
    returned: optional
"""

import json

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.urls import fetch_url

try:
    from urllib import urlencode
except ImportError:  # For Python 3
    from urllib.parse import urlencode


def exit_failed(module, msg, response=None):
    result = {"msg": msg, "changed": False, "failed": True, "response": response}
    module.fail_json(**result)


def exit_changed(module, msg, response=None):
    result = {"msg": msg, "changed": True, "failed": False, "response": response}
    module.exit_json(**result)


def exit_ok(module, msg, response=None):
    result = {"msg": msg, "changed": False, "failed": False, "response": response}
    module.exit_json(**result)


def get_rules_in_ruleset(module, base_url, headers, ruleset):
    api_endpoint = "/domain-types/rule/collections/all"

    params = {
        "ruleset_name": ruleset,
    }

    url = "%s%s?%s" % (base_url, api_endpoint, urlencode(params))

    response, info = fetch_url(
        module, url, module.jsonify(params), headers=headers, method="GET"
    )

    if info["status"] != 200:
        exit_failed(
            module,
            "Error calling API. HTTP code %d. Details: %s, "
            % (info["status"], info["body"]),
        )
    return json.loads(response.read().decode("utf-8"))


def get_existing_rule(module, base_url, headers, ruleset, rule):
    # Get rules in ruleset
    rules = get_rules_in_ruleset(module, base_url, headers, ruleset)
    if rules is not None:
        # Loop through all rules
        for r in rules.get("value"):
            # Check if conditions, properties and values are the same
            if (
                sorted(r["extensions"]["conditions"]) == sorted(rule["conditions"])
                and sorted(r["extensions"]["properties"]) == sorted(rule["properties"])
                and sorted(r["extensions"]["value_raw"]) == sorted(rule["value_raw"])
            ):
                # If they are the same, return the ID
                return r["id"]
    return None


def create_rule(module, base_url, headers, ruleset, rule):
    api_endpoint = "/domain-types/rule/collections/all"

    params = {
        "ruleset": ruleset,
        "folder": rule["folder"],
        "properties": rule["properties"],
        "value_raw": rule["value_raw"],
        "conditions": rule["conditions"],
    }

    url = base_url + api_endpoint

    response, info = fetch_url(
        module, url, module.jsonify(params), headers=headers, method="POST"
    )

    if info["status"] != 200:
        exit_failed(
            module,
            "Error calling API. HTTP code %d. Details: %s, "
            % (info["status"], info["body"]),
        )


def delete_rule(module, base_url, headers, rule_id):
    api_endpoint = "/objects/rule/"

    url = "%s%s%s" % (base_url, api_endpoint, rule_id)

    response, info = fetch_url(module, url, headers=headers, method="DELETE")

    if info["status"] != 204:
        exit_failed(
            module,
            "Error calling API. HTTP code %d. Details: %s, "
            % (info["status"], info["body"]),
        )


def run_module():
    # define available arguments/parameters a user can pass to the module
    module_args = dict(
        server_url=dict(type="str", required=True),
        site=dict(type="str", required=True),
        automation_user=dict(type="str", required=True),
        automation_secret=dict(type="str", required=True, no_log=True),
        ruleset=dict(type="str", required=True),
        rule=dict(type="dict", required=False),
        state=dict(type="str", default="present", choices=["present", "absent"]),
    )

    module = AnsibleModule(argument_spec=module_args, supports_check_mode=False)

    # Use the parameters to initialize some common variables
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

    # Get the variables
    ruleset = module.params.get("ruleset", "")
    rule = module.params.get("rule", "")

    if rule is not None:

        # Check if required params to create a rule are given
        if rule.get("folder") is None or rule.get("folder") == "":
            rule["folder"] = "/"
        if rule.get("properties") is None or rule.get("properties") == "":
            exit_failed(module, "Rule properties are required")
        if rule.get("value_raw") is None or rule.get("value_raw") == "":
            exit_failed(module, "Rule value_raw is required")
        # Default to all hosts if conditions arent given
        if rule.get("conditions") is None or rule.get("conditions") == "":
            rule["conditions"] = {
                "host_tags": [],
                "host_labels": [],
                "service_labels": [],
            }
        # Get ID of rule that is the same as the given options
        rule_id = get_existing_rule(module, base_url, headers, ruleset, rule)
        # If rule exists
        if rule_id is not None:
            # If state is absent, delete the rule
            if module.params.get("state") == "absent":
                delete_rule(module, base_url, headers, rule_id)
                exit_changed(module, "Deleted rule")
            # If state is present, do nothing
            else:
                exit_ok(module, "Rule already exists")
        # If rule does not exist
        else:
            # If state is present, create the rule
            if module.params.get("state") == "present":
                create_rule(module, base_url, headers, ruleset, rule)
                exit_changed(module, "Created rule")
            else:
                # If state is absent, do nothing
                exit_ok(module, "Rule did not exist")

    # No action can be taken, just return the rules in the ruleset
    else:
        response = get_rules_in_ruleset(module, base_url, headers, ruleset)
        exit_ok(module, "Got rules in ruleset", response)
    # Fallback
    exit_failed(module, "Unknown error")


def main():
    run_module()


if __name__ == "__main__":
    main()
