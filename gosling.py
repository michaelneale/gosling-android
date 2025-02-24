import base64
import io
import json
import os
import subprocess
import time
import xml.etree.ElementTree as ET
from typing import Any

import requests
from PIL import Image
from bs4 import BeautifulSoup
from openai import OpenAI
from tenacity import retry, wait_fixed, stop_after_attempt

from databricks_auth import get_client

REPOSITORY_ROOT = os.path.dirname(__file__)

SYSTEM_MESSAGE = (
    "You are an assistant managing the users android phone. The user does not have access to the phone. "
    "You will autonomously complete complex tasks on the phone and report back to the user when "
    "done. Try to avoid asking extra questions. You accomplish this by starting apps on the phone "
    "and interacting with them\n"
    "After each tool call you will see the state of the phone by way of a screenshot and a ui hierarchy "
    "produced using 'adb shell uiautomator dump'. One or both might be simplified or omitted to save space. "
    "Use this to verify your work\n"
    "The phone has a screen resolution of {width}x{height} pixels\n"
    "The phone has the following apps installed:\n{app_info}\n"
    "Before getting started, explicitly state the steps you want to take and which app(s) you want "
    "use to accomplish that task. For example, open the contacts app to find out Joe's phone number. "
    "Then after each step verify that the step was completed successfully by looking at the screen and "
    "the ui hierarchy dump. If the step was not completed successfully, try to recover. When you start "
    "an app, make sure the app is in the state you expect it to be in. If it is not, try to recover.\n"
    "After each tool call and before the next step, write down what you see on the screen that helped "
    "you resolve this step. If you can't consider retrying."
)


def json_function(name, description, **properties):
    props = {
        name: {"type": type_, "description": desc}
        for name, (type_, desc) in properties.items()
    }

    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": props,
                "required": [*properties.keys()],
            },
        },
    }


TOOL_DEFINITIONS = [
    json_function("home", "Press the home button on the device"),
    json_function(
        "click",
        "Click at specific coordinates on the device screen",
        x=("integer", "X coordinate to click"),
        y=("integer", "Y coordinate to click"),
    ),
    json_function(
        "enter_text",
        "Enter text into the current text field. Text will automatically submit unless you end on ---",
        text=("string", "Text to enter"),
    ),
    # json_function("screenshot", "Take a screenshot of the current device screen"),
    json_function(
        "start_app",
        "Start an application by its package name",
        package_name=("string", "Full package name of the app to start"),
    ),
    json_function(
        "select_text",
        "Select text on the screen between two coordinate points",
        start_x=("integer", "Starting X coordinate for text selection"),
        start_y=("integer", "Starting Y coordinate for text selection"),
        end_x=("integer", "Ending X coordinate for text selection"),
        end_y=("integer", "Ending Y coordinate for text selection"),
    ),
    json_function(
        "swipe",
        "Swipe from one point to another on the screen for example to scroll",
        start_x=("integer", "Starting X coordinate"),
        start_y=("integer", "Starting Y coordinate"),
        end_x=("integer", "Ending X coordinate"),
        end_y=("integer", "Ending Y coordinate"),
        duration=(
            "integer",
            "Duration of swipe in milliseconds. Default is 300. Use longer duration (500+) for text selection",
        ),
    ),
    json_function(
        "copy_selected",
        "Copy currently selected text to clipboard and return the value",
    ),
]

ROLE_ASSISTANT = "assistant"
ROLE_USER = "user"
UI_HIERARCHY_PROMPT = "\nHere's the current UI hierarchy:\n"
SCREEN_DUMP_PROMPT = "\nHere's the current screen dump (base64 encoded jpeg):\n"


def get_ui_hierarchy(clean: bool = False) -> str:
    run_shell_command(
        ["uiautomator", "dump", "/sdcard/window_dump.xml"], log_message=""
    )
    result = run_shell_command(
        ["cat", "/sdcard/window_dump.xml"], log_message=""
    ).decode("utf-8")
    if clean:
        result = clean_hierarchy(result)
    return result


def process_screenshot(screenshot_data: bytes) -> bytes:
    """Process and optimize screenshot."""
    MAX_WIDTH = 768

    img = Image.open(io.BytesIO(screenshot_data))

    if img.width > MAX_WIDTH:
        ratio = MAX_WIDTH / img.width
        new_height = int(img.height * ratio)
        img = img.resize((MAX_WIDTH, new_height), Image.Resampling.LANCZOS)

    output = io.BytesIO()
    img = img.convert("RGB")
    img.save(output, format="JPEG", quality=85)
    img.save("screenshot.jpg")
    return output.getvalue()


def take_screenshot() -> str:
    screenshot_data = run_shell_command(["screencap", "-p"], log_message="")
    processed_data = process_screenshot(screenshot_data)
    b64_data = base64.b64encode(processed_data).decode("utf-8")
    return b64_data


def clean_node(element):
    attrs_to_remove = []

    for attr, value in element.attrib.items():
        # Remove if value is empty string or "false"
        if value == "" or value.lower() == "false":
            attrs_to_remove.append(attr)

    for attr in attrs_to_remove:
        element.attrib.pop(attr)

    for child in element:
        clean_node(child)


def clean_hierarchy(xml_string):
    root = ET.fromstring(xml_string)
    clean_node(root)
    return ET.tostring(root, encoding="unicode", method="xml")


def clean_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def should_keep(entry: dict[str, Any]) -> bool:
        return entry["type"] != "image" and not entry["text"].startswith(
            UI_HIERARCHY_PROMPT
        )

    budget = 2
    for idx, msg in enumerate(reversed(messages)):
        content = msg.get("content")
        if isinstance(content, list):
            budget -= 1
            if budget < 0:
                msg["content"] = [entry for entry in content if should_keep(entry)]

    return messages


def handle_tool_calls(tool_calls: list[dict[str, Any]]) -> list[dict[str, str]]:
    tool_results = []

    for tool_call in tool_calls:

        def add_result(output: str, skip_log=False):
            tool_results.append(
                {
                    "tool_call_id": tool_call["id"],
                    "output": output,
                }
            )
            if not skip_log:
                print(output)

        try:
            function = tool_call["function"]
            args = (
                json.loads(function["arguments"]) if function.get("arguments") else {}
            )

            if function["name"] == "home":
                run_shell_command(["input", "keyevent", "KEYCODE_HOME"])
                add_result("Pressed home button")

            elif function["name"] == "click":
                x, y = args["x"], args["y"]
                run_shell_command(["input", "tap", str(x), str(y)])
                add_result(f"Clicked at coordinates ({x}, {y})")

            elif function["name"] == "enter_text":
                text = args["text"]
                for line in text.split("\n"):
                    if skip_auto_submit := line.endswith("---"):
                        line = line[:-3]
                    line = line.replace("'", " ")
                    line = line.replace("€", "EUR")
                    line = line.replace("ö", "o")
                    run_shell_command(["input", "text", f"'{line}'"])
                    if not skip_auto_submit:
                        # if we do this immediately it gets ignored?
                        time.sleep(0.25)
                        run_shell_command(["input", "keyevent", "KEYCODE_ENTER"])
                add_result(f"Entered text: '{text}'")

            elif function["name"] == "screenshot":
                b64_data = take_screenshot()
                add_result(
                    "Here's the screenshot b64 encoded:\n"
                    + json.dumps(
                        {"type": "image", "data": b64_data, "mime_type": "image/jpeg"}
                    ),
                    skip_log=True,
                )

            elif function["name"] == "start_app":
                package_name = args["package_name"]
                run_shell_command(
                    [
                        "monkey",
                        "-p",
                        package_name,
                        "-c",
                        "android.intent.category.LAUNCHER",
                        "1",
                    ],
                    log_message=f"Starting app: {package_name}",
                )
                add_result(f"Started app: {package_name}")
            elif function["name"] == "select_text":
                start_x, start_y = args["start_x"], args["start_y"]
                end_x, end_y = args["end_x"], args["end_y"]

                # Long press at starting point (swipe with same start/end coordinates)
                run_shell_command(
                    [
                        "input",
                        "swipe",
                        str(start_x),
                        str(start_y),
                        str(start_x),
                        str(start_y),
                        "800",
                    ]
                )  # 800ms for long press

                time.sleep(0.5)  # Wait for selection handles to appear

                # Now drag to select
                run_shell_command(
                    [
                        "input",
                        "swipe",
                        str(start_x),
                        str(start_y),
                        str(end_x),
                        str(end_y),
                        "300",
                    ]
                )

                add_result(
                    f"Selected text from ({start_x}, {start_y}) to ({end_x}, {end_y})"
                )
            elif function["name"] == "swipe":
                start_x = args["start_x"]
                start_y = args["start_y"]
                end_x = args["end_x"]
                end_y = args["end_y"]
                duration = args.get("duration", 300)  # Default duration of 300ms

                run_shell_command(
                    [
                        "input",
                        "swipe",
                        str(start_x),
                        str(start_y),
                        str(end_x),
                        str(end_y),
                        str(duration),
                    ]
                )

                add_result(f"Swiped from ({start_x}, {start_y}) to ({end_x}, {end_y})")
            elif function["name"] == "copy_selected":
                run_shell_command(["input", "keyevent", "KEYCODE_COPY"])
                clipboard_content = run_shell_command(
                    ["service", "call", "clipboard", "get_clipboard"]
                ).decode()
                add_result(f"Clipboard contents: {clipboard_content}")
            else:
                add_result(f"Unknown tool call: {function['name']}")

        except (
            subprocess.CalledProcessError,
            json.JSONDecodeError,
            KeyError,
            OSError,
        ) as e:
            add_result(f"Error processing tool call: {str(e)}")

    tool_results[-1]["output"] = [
        {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/jpeg",
                "data": take_screenshot(),
            },
        },
        {"type": "text", "text": UI_HIERARCHY_PROMPT + get_ui_hierarchy(clean=True)},
        {"type": "text", "text": tool_results[-1]["output"]},
    ]

    return tool_results


@retry(wait=wait_fixed(2), stop=stop_after_attempt(2), reraise=True)
def call_llm(
    client, messages: list, tools: list, temperature=0.1
) -> tuple[dict, list[dict]]:
    """Call either OpenAI if key exists, otherwise Bedrock through Databricks proxy.

    Returns the response and the messages so far
    """

    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        print("Calling OpenAI")

    while True:
        with open("messages.json", "w") as f:
            json.dump(messages, f, indent=2)
        if openai_key:
            openai_client = OpenAI(api_key=openai_key)
            response = openai_client.chat.completions.create(
                model="o1-mini",
                messages=messages,
                temperature=temperature,
                tools=tools,
            )
            response = response.model_dump()
        else:
            payload = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 4096,
                "messages": messages,
                "temperature": temperature,
                "top_p": 0.999,
                "tools": TOOL_DEFINITIONS,
            }
            response = client.post(
                "serving-endpoints/claude-3-5-sonnet-2/invocations", json=payload
            )
            if response.status_code != 200:
                raise Exception(
                    f"Error calling Claude: {response.status_code} - {response.text}"
                )

            response = response.json()

        # first call 1922 tokens
        # second call 20790

        assistant_message = response["choices"][0]["message"]
        # print("usage:", response["usage"])
        if "content" in assistant_message:
            content = assistant_message["content"]
            if not content:
                del assistant_message["content"]
        else:
            content = None
        if content:
            print(content)

        messages = clean_messages(messages)

        if not (tool_calls := assistant_message.get("tool_calls")):
            return response, messages

        tool_results = handle_tool_calls(tool_calls)

        messages.append(assistant_message)
        for result in tool_results:
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": result["tool_call_id"],
                    "content": result["output"],
                }
            )


def run_shell_command(command: list[str], log_message: str | None = None) -> bytes:
    try:
        result = subprocess.run(
            ["adb", "shell"] + command, capture_output=True, check=True
        )
        stdout = result.stdout
        if log_message is None:
            log_message = " ".join(command)
        # if log_message:
        #     print("adb>", log_message, stdout.decode("utf-8"))
        return stdout
    except subprocess.CalledProcessError as e:
        raise Exception(f"Command failed: {e}")


def scrape_play_store_title(package_name: str) -> str | None:
    url = f"https://play.google.com/store/apps/details?id={package_name}"
    response = requests.get(url)
    if response.status_code != 200:
        return None

    soup = BeautifulSoup(response.text, "html.parser")
    title = soup.find("span", {"itemprop": "name"})
    return title.text if title else None


def get_installed_apps() -> dict[str, str]:
    cache_file = "app_cache.json"
    if os.path.exists(cache_file):
        with open(cache_file, "r") as f:
            app_info = json.load(f)
    else:
        print("Getting list of installed apps")
        output = run_shell_command(["pm", "list", "packages"], log_message="")
        packages = [
            stripped.replace("package:", "")
            for line in output.decode("utf-8").split("\n")
            if (stripped := line.strip())
        ]

        app_info = {package: scrape_play_store_title(package) for package in packages}
        with open(cache_file, "w") as f:
            json.dump(app_info, f)
        print("done.")

    return {pkg: desc for pkg, desc in app_info.items() if desc}


def initialize_device() -> tuple[int, int]:
    result = subprocess.run(["adb", "devices"], capture_output=True, text=True)
    if "device" not in result.stdout:
        raise Exception("No device connected")

    result = subprocess.run(
        ["adb", "shell", "wm", "size"], capture_output=True, text=True
    )
    size_str = [l for l in result.stdout.split("\n") if "Physical size" in l][0]
    width, height = map(int, size_str.split()[-1].split("x"))
    return width, height


def close_all_apps():
    # Get the list of running apps
    output = run_shell_command(["ps", "-A"], log_message="").decode("utf-8")
    lines = output.splitlines()

    # Iterate over each line to find running apps
    for line in lines:
        if "u0_a" in line:  # This is a common user ID prefix for apps
            parts = line.split()
            if len(parts) > 8:
                package_name = parts[-1]
                # Force stop the app
                run_shell_command(["am", "force-stop", package_name])
                print(f"Closed app: {package_name}")


def main():
    os.system("cls" if os.name == "nt" else "clear")

    width, height = initialize_device()
    app_info = get_installed_apps()

    formatted_app_info = "\n".join(
        f"{desc} ({pkg})" for pkg, desc in app_info.items() if desc
    )

    system_prompt = SYSTEM_MESSAGE.format(
        width=width, height=height, app_info=formatted_app_info
    )
    messages = [{"role": "system", "content": system_prompt}]

    client = get_client()
    print("\nGosling is ready to help you do something. What will it be?")

    user_input = input("\n🪿 ").strip()
    # user_input = (
    #     "Find the best sushi in Berlin, Germany, find out how to get there by public transport from "
    #     "Brunnenstrasse 194. "
    #     "Also check on Uber how much it would be to go by car, but don't order a car. "
    #     "Then email the results to douwe@block.xyz"
    # )

    # user_input = "Create a new google doc and write a funny poem about cats"

    messages.append({"role": "user", "content": user_input})
    response, messages = call_llm(client, messages, TOOL_DEFINITIONS)
    print("\n\033[32mAssistant:", response["choices"][0]["message"]["content"], "\033[0m")


if __name__ == "__main__":
    main()
