"""Textual TUI form for monitor configuration.

Provides an interactive form-based interface with a step-by-step wizard
for users to input monitor configuration with real-time validation using Pydantic.
"""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import (
    Button,
    Input,
    Label,
    Static,
    Switch,
)

from website_monitor_cli.models import MonitorConfigForm


class ErrorMessage(Static):
    """Widget to display validation errors."""
    
    DEFAULT_CSS = """
    ErrorMessage {
        color: $error;
        text-style: bold;
        height: auto;
        margin: 0 0 1 0;
    }
    """


class SuccessMessage(Static):
    """Widget to display success messages."""
    
    DEFAULT_CSS = """
    SuccessMessage {
        color: $success;
        text-style: bold;
        height: auto;
        margin: 0 0 1 0;
    }
    """


class WarningMessage(Static):
    """Widget to display warning messages."""
    
    DEFAULT_CSS = """
    WarningMessage {
        color: $warning;
        height: auto;
        margin: 0 0 1 0;
    }
    """


class StepIndicator(Static):
    """Widget to display a step in the wizard progress."""
    
    DEFAULT_CSS = """
    StepIndicator {
        width: auto;
        padding: 0 2;
        text-align: center;
    }
    StepIndicator.active {
        color: $success;
        text-style: bold underline;
    }
    StepIndicator.completed {
        color: $success;
    }
    StepIndicator.pending {
        color: $text-muted;
    }
    """
    
    def __init__(self, step_num: int, title: str, state: str = "pending") -> None:
        self.step_num = step_num
        self.title = title
        self.state = state
        super().__init__()
    
    def on_mount(self) -> None:
        self.update(f"{self.step_num}. {self.title}")
        self.set_state(self.state)
    
    def set_state(self, state: str) -> None:
        """Set the state: pending, active, or completed."""
        self.state = state
        self.remove_class("pending", "active", "completed")
        self.add_class(state)


class FormField(Container):
    """A form field with label, input, and error display."""
    
    DEFAULT_CSS = """
    FormField {
        height: auto;
        margin: 0 0 1 0;
    }
    FormField Label {
        width: 100%;
    }
    FormField Input {
        width: 100%;
    }
    FormField .field-description {
        color: $text-muted;
        text-style: italic;
        margin: 0 0 0 1;
    }
    """
    
    def __init__(
        self,
        label: str,
        input_widget: Input | None = None,
        description: str = "",
        **kwargs: Any,
    ) -> None:
        self.label_text = label
        self.input_widget = input_widget or Input()
        self.description_text = description
        super().__init__(**kwargs)
    
    def compose(self) -> ComposeResult:
        yield Label(self.label_text)
        if self.description_text:
            yield Label(self.description_text, classes="field-description")
        yield self.input_widget
        yield ErrorMessage("", id=f"{self.input_widget.id}_error" if self.input_widget.id else None)
    
    @property
    def value(self) -> str:
        """Get the input value."""
        return self.input_widget.value
    
    @value.setter
    def value(self, val: str) -> None:
        """Set the input value."""
        self.input_widget.value = val
    
    def show_error(self, message: str) -> None:
        """Show an error message."""
        error_widget = self.query_one(ErrorMessage)
        error_widget.update(message)
        error_widget.styles.color = "red"
    
    def clear_error(self) -> None:
        """Clear the error message."""
        error_widget = self.query_one(ErrorMessage)
        error_widget.update("")


class Step1Screen(Container):
    """Step 1: URL and SSL Verification."""
    
    def __init__(self, form_data: dict[str, Any], defaults: dict[str, Any]) -> None:
        self.form_data = form_data
        self.defaults = defaults
        super().__init__()
    
    def compose(self) -> ComposeResult:
        with Container(id="step-container"):
            yield Static("Website URL & SSL Settings", classes="step-title")
            
            url_field = FormField(
                "Website URL *",
                Input(
                    placeholder="https://example.com",
                    id="url_input",
                ),
                description="The URL to monitor (must start with http:// or https://)",
            )
            url_field.input_widget.value = self.form_data.get("url", self.defaults.get("url", ""))
            yield url_field
            
            # SSL Verification
            with Horizontal(classes="switch-row"):
                yield Label("Verify SSL Certificates:", classes="switch-label")
                yield Switch(
                    value=bool(self.form_data.get("verify_ssl") if self.form_data.get("verify_ssl") is not None else self.defaults.get("verify_ssl", True)),
                    id="verify_ssl_switch",
                )
            yield Label(
                "Disable to bypass SSL errors (e.g., self-signed certs)",
                classes="field-description",
            )
            
            with Horizontal(classes="button-row"):
                yield Button("✗ Cancel", variant="error", id="cancel_btn")
                yield Button("Next →", variant="primary", id="next_btn")
            
            yield Static("", id="step1-error")


class Step2Screen(Container):
    """Step 2: Basic Settings (interval, timeout, max_checks, background)."""
    
    def __init__(self, form_data: dict[str, Any], defaults: dict[str, Any]) -> None:
        self.form_data = form_data
        self.defaults = defaults
        super().__init__()
    
    def compose(self) -> ComposeResult:
        with Container(id="step-container"):
            yield Static("Basic Monitoring Settings", classes="step-title")
            
            interval_field = FormField(
                "Check Interval (seconds)",
                Input(
                    placeholder="60",
                    id="interval_input",
                ),
                description="Time between checks (5-86400 seconds, default: 60)",
            )
            interval_field.input_widget.value = str(
                self.form_data.get("interval") or self.defaults.get("interval") or 60
            )
            yield interval_field
            
            timeout_field = FormField(
                "HTTP Timeout (seconds)",
                Input(
                    placeholder="10",
                    id="timeout_input",
                ),
                description="Request timeout (1-300 seconds, default: 10)",
            )
            timeout_field.input_widget.value = str(
                self.form_data.get("timeout") or self.defaults.get("timeout") or 10
            )
            yield timeout_field
            
            max_checks_field = FormField(
                "Max Checks (optional)",
                Input(
                    placeholder="Leave empty for unlimited",
                    id="max_checks_input",
                ),
                description="Maximum number of checks before stopping",
            )
            default_max = self.form_data.get("max_checks") or self.defaults.get("max_checks")
            max_checks_field.input_widget.value = str(default_max) if default_max else ""
            yield max_checks_field
            
            # Background Mode
            with Horizontal(classes="switch-row"):
                yield Label("Run in Background:", classes="switch-label")
                yield Switch(
                    value=bool(self.form_data.get("background") if self.form_data.get("background") is not None else self.defaults.get("background", False)),
                    id="background_switch",
                )
            yield Label(
                "Enable to run as a daemon job (allows stop/status/logs)",
                classes="field-description",
            )
            
            with Horizontal(classes="button-row"):
                yield Button("← Previous", variant="default", id="prev_btn")
                yield Button("Next →", variant="primary", id="next_btn")
            
            yield Static("", id="step2-error")


class Step3Screen(Container):
    """Step 3: Webhook Settings."""
    
    def __init__(self, form_data: dict[str, Any], defaults: dict[str, Any]) -> None:
        self.form_data = form_data
        self.defaults = defaults
        super().__init__()
    
    def compose(self) -> ComposeResult:
        with Container(id="step-container"):
            yield Static("Webhook Notifications (Optional)", classes="step-title")
            
            webhook_field = FormField(
                "Webhook URL",
                Input(
                    placeholder="https://hooks.example.com/alert",
                    id="webhook_url_input",
                ),
                description="URL to POST to when checks fail (optional)",
            )
            webhook_field.input_widget.value = (
                self.form_data.get("webhook_url") or self.defaults.get("webhook_url") or ""
            )
            yield webhook_field
            
            payload_field = FormField(
                "Custom Payload (JSON)",
                Input(
                    placeholder='{"site":"{url}","error":"{error}"}',
                    id="webhook_payload_input",
                ),
                description=(
                    "Valid placeholders: {url}, {status_code}, "
                    "{error}, {timestamp}, {response_time}"
                ),
            )
            payload_field.input_widget.value = (
                self.form_data.get("webhook_payload") or self.defaults.get("webhook_payload") or ""
            )
            yield payload_field
            
            with Horizontal(classes="button-row"):
                yield Button("← Previous", variant="default", id="prev_btn")
                yield Button("✓ Start Monitor", variant="success", id="submit_btn")
            
            yield Static("", id="step3-error")


class MonitorFormApp(App[dict[str, Any] | None]):
    """Textual app for monitor configuration form with step-by-step wizard.
    
    Returns the form data as a dictionary when submitted, or None if cancelled.
    """
    
    CSS = """
    Screen {
        align: center middle;
    }
    
    #wizard-container {
        width: 80;
        height: auto;
        border: solid $primary;
        padding: 1 2;
    }
    
    #wizard-header {
        text-align: center;
        margin: 0 0 1 0;
    }
    
    #form-title {
        text-align: center;
        text-style: bold underline;
        margin: 0 0 1 0;
    }
    
    #step-indicator-row {
        height: auto;
        align: center middle;
        margin: 0 0 2 0;
        border-bottom: solid $primary-darken-2;
        padding-bottom: 1;
    }
    
    #step-content {
        width: 100%;
        height: auto;
    }
    
    #abort-row {
        height: auto;
        margin: 1 0 0 0;
        align: center middle;
        border-top: solid $primary-darken-2;
        padding-top: 1;
    }
    
    #step-container {
        width: 100%;
        height: auto;
        padding: 1 0;
    }
    
    .step-title {
        text-style: bold;
        margin: 0 0 2 0;
        color: $primary;
        text-align: center;
    }
    
    .switch-row {
        height: auto;
        margin: 1 0 0 0;
    }
    
    .switch-label {
        width: auto;
        margin-right: 1;
    }
    
    .button-row {
        height: auto;
        margin: 2 0 0 0;
        align: center middle;
    }
    
    .button-row Button {
        margin: 0 1;
    }
    
    .field-description {
        color: $text-muted;
        text-style: italic;
        margin: 0 0 1 0;
    }
    
    Switch {
        margin: 0;
    }
    
    #step1-error, #step2-error, #step3-error {
        height: auto;
        margin: 1 0 0 0;
        text-align: center;
        color: $error;
    }
    """
    
    BINDINGS = [
        ("ctrl+q", "quit", "Quit"),
    ]
    
    def __init__(self, defaults: dict[str, Any] | None = None) -> None:
        self.defaults = defaults or {}
        self.form_data: dict[str, Any] = {}
        self.result: dict[str, Any] | None = None
        self.current_step = 1
        super().__init__()
    
    def compose(self) -> ComposeResult:
        with Container(id="wizard-container"):
            yield Static("Website Monitor Configuration", id="form-title")
            
            # Step indicators
            with Horizontal(id="step-indicator-row"):
                yield StepIndicator(1, "URL & SSL", "active")
                yield StepIndicator(2, "Basic Settings", "pending")
                yield StepIndicator(3, "Webhook", "pending")
            
            # Content area for steps
            yield Container(id="step-content")
            
            # Global abort button at bottom
            with Horizontal(id="abort-row"):
                yield Button("✗ Abort", variant="error", id="abort_btn")
    
    def on_mount(self) -> None:
        """Mount the first step."""
        self.show_step(1)
    
    def show_step(self, step: int) -> None:
        """Show the specified step screen."""
        self.current_step = step
        
        # Update step indicators
        indicators = self.query(StepIndicator)
        for i, indicator in enumerate(indicators, 1):
            if i < step:
                indicator.set_state("completed")
            elif i == step:
                indicator.set_state("active")
            else:
                indicator.set_state("pending")
        
        # Update content
        content = self.query_one("#step-content", Container)
        content.remove_children()
        
        if step == 1:
            content.mount(Step1Screen(self.form_data, self.defaults))
        elif step == 2:
            content.mount(Step2Screen(self.form_data, self.defaults))
        elif step == 3:
            content.mount(Step3Screen(self.form_data, self.defaults))
    
    def collect_step_data(self, step: int) -> bool:
        """Collect data from the current step. Returns True if successful."""
        if step == 1:
            url = self.query_one("#url_input", Input).value.strip()
            verify_ssl = self.query_one("#verify_ssl_switch", Switch).value
            self.form_data["url"] = url
            self.form_data["verify_ssl"] = verify_ssl
            
            # Validate URL
            if not url:
                error_widget = self.query_one("#step1-error", Static)
                error_widget.update("⚠ URL is required")
                return False
            if not (url.startswith("http://") or url.startswith("https://")):
                error_widget = self.query_one("#step1-error", Static)
                error_widget.update("⚠ URL must start with http:// or https://")
                return False
            return True
            
        elif step == 2:
            interval_str = self.query_one("#interval_input", Input).value.strip()
            timeout_str = self.query_one("#timeout_input", Input).value.strip()
            max_checks_str = self.query_one("#max_checks_input", Input).value.strip()
            background = self.query_one("#background_switch", Switch).value
            
            # Parse and validate numbers
            try:
                interval = int(interval_str) if interval_str else 60
                if interval < 5 or interval > 86400:
                    raise ValueError("Interval must be between 5 and 86400")
            except ValueError as e:
                error_widget = self.query_one("#step2-error", Static)
                error_widget.update(f"⚠ Invalid interval: {e}")
                return False
            
            try:
                timeout = int(timeout_str) if timeout_str else 10
                if timeout < 1 or timeout > 300:
                    raise ValueError("Timeout must be between 1 and 300")
            except ValueError as e:
                error_widget = self.query_one("#step2-error", Static)
                error_widget.update(f"⚠ Invalid timeout: {e}")
                return False
            
            max_checks = None
            if max_checks_str:
                try:
                    max_checks = int(max_checks_str)
                    if max_checks < 1 or max_checks > 10000:
                        raise ValueError("Max checks must be between 1 and 10000")
                except ValueError as e:
                    error_widget = self.query_one("#step2-error", Static)
                    error_widget.update(f"⚠ Invalid max checks: {e}")
                    return False
            
            self.form_data["interval"] = interval
            self.form_data["timeout"] = timeout
            self.form_data["max_checks"] = max_checks
            self.form_data["background"] = background
            return True
            
        elif step == 3:
            webhook_url = self.query_one("#webhook_url_input", Input).value.strip()
            webhook_payload = self.query_one("#webhook_payload_input", Input).value.strip()
            
            # Validate webhook URL if provided
            if webhook_url:
                if not (webhook_url.startswith("http://") or webhook_url.startswith("https://")):
                    error_widget = self.query_one("#step3-error", Static)
                    error_widget.update("⚠ Webhook URL must start with http:// or https://")
                    return False
            
            # Validate webhook payload if provided
            if webhook_payload:
                import json
                try:
                    json.loads(webhook_payload)
                except json.JSONDecodeError:
                    error_widget = self.query_one("#step3-error", Static)
                    error_widget.update("⚠ Webhook payload must be valid JSON")
                    return False
            
            self.form_data["webhook_url"] = webhook_url if webhook_url else None
            self.form_data["webhook_payload"] = webhook_payload if webhook_payload else None
            return True
        
        return False
    
    def validate_all(self) -> tuple[bool, dict[str, Any], list[dict[str, str]]]:
        """Validate all form data using Pydantic.
        
        Returns: (is_valid, data_or_empty, errors_or_empty)
        """
        try:
            validated = MonitorConfigForm(**self.form_data)
            return True, validated.model_dump(), []
        except ValidationError as e:
            errors: list[dict[str, str]] = []
            for error in e.errors():
                field = str(error["loc"][0]) if error["loc"] else "general"
                message = error["msg"]
                errors.append({"field": field, "message": message})
            return False, {}, errors
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        button_id = event.button.id
        
        if button_id == "cancel_btn":
            self.action_cancel()
        elif button_id == "next_btn":
            if self.collect_step_data(self.current_step):
                if self.current_step < 3:
                    self.show_step(self.current_step + 1)
                else:
                    self.action_submit()
        elif button_id == "prev_btn":
            # Save current data before going back
            self.collect_step_data(self.current_step)
            if self.current_step > 1:
                self.show_step(self.current_step - 1)
        elif button_id == "submit_btn":
            if self.collect_step_data(self.current_step):
                self.action_submit()
        elif button_id == "abort_btn":
            self.action_cancel()
    
    def action_submit(self) -> None:
        """Submit the form."""
        is_valid, data, errors = self.validate_all()
        
        if is_valid:
            self.result = data
            self.exit(data)
        else:
            # Show errors on current step
            # errors already defined from validate_all
            error_widget = self.query_one(f"#step{self.current_step}-error", Static)
            error_messages = [f"{e['field']}: {e['message']}" for e in errors]
            error_widget.update("\n".join(error_messages))
    
    def action_cancel(self) -> None:
        """Cancel the form."""
        self.result = None
        self.exit(None)
    
    async def action_quit(self) -> None:
        """Quit the app."""
        self.result = None
        self.exit(None)


def run_monitor_form(defaults: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Run the monitor form and return the result.
    
    Args:
        defaults: Optional default values for form fields.
    
    Returns:
        The validated form data as a dictionary, or None if cancelled.
    """
    app = MonitorFormApp(defaults=defaults)
    return app.run()


class QuickCheckFormApp(App[dict[str, Any] | None]):
    """Simplified form for quick single URL check."""
    
    CSS = """
    Screen {
        align: center middle;
    }
    
    #form-container {
        width: 60;
        height: auto;
        border: solid $primary;
        padding: 1 2;
    }
    
    #form-title {
        text-align: center;
        text-style: bold underline;
        margin: 0 0 1 0;
    }
    
    #button-row {
        height: auto;
        margin: 2 0 0 0;
        align: center middle;
    }
    
    #button-row Button {
        margin: 0 1;
    }
    """
    
    BINDINGS = [
        ("ctrl+q", "quit", "Quit"),
        ("ctrl+s", "submit", "Submit"),
    ]
    
    def __init__(self, defaults: dict[str, Any] | None = None) -> None:
        self.defaults = defaults or {}
        self.result: dict[str, Any] | None = None
        super().__init__()
    
    def compose(self) -> ComposeResult:
        with Container(id="form-container"):
            yield Static("Quick Website Check", id="form-title")
            
            url_field = FormField(
                "Website URL *",
                Input(
                    placeholder="https://example.com",
                    id="url_input",
                ),
                description="The URL to check",
            )
            url_field.input_widget.value = self.defaults.get("url", "")
            yield url_field
            
            timeout_field = FormField(
                "Timeout (seconds)",
                Input(
                    placeholder="10",
                    id="timeout_input",
                ),
                description="Request timeout (1-300 seconds)",
            )
            timeout_field.input_widget.value = str(self.defaults.get("timeout", 10))
            yield timeout_field
            
            with Horizontal():
                yield Label("Verify SSL: ")
                yield Switch(
                    value=self.defaults.get("verify_ssl", True),
                    id="verify_ssl_switch",
                )
            
            with Horizontal(id="button-row"):
                yield Button("✓ Check", variant="success", id="submit_btn")
                yield Button("✗ Cancel", variant="error", id="cancel_btn")
            
            yield Static("", id="result-message")
    
    def get_form_values(self) -> dict[str, Any]:
        """Extract values from form fields."""
        # Get text field values
        url = self.query_one("#url_input", Input).value.strip()
        interval_str = self.query_one("#interval_input", Input).value.strip()
        timeout_str = self.query_one("#timeout_input", Input).value.strip()
        max_checks_str = self.query_one("#max_checks_input", Input).value.strip()
        webhook_url = self.query_one("#webhook_url_input", Input).value.strip()
        webhook_payload = self.query_one("#webhook_payload_input", Input).value.strip()
        
        # Get switch values
        background = self.query_one("#background_switch", Switch).value
        verify_ssl = self.query_one("#verify_ssl_switch", Switch).value
        
        # Convert numeric fields
        try:
            interval = int(interval_str) if interval_str else 60
        except ValueError:
            interval = 60
        
        try:
            timeout = int(timeout_str) if timeout_str else 10
        except ValueError:
            timeout = 10
        
        max_checks = None
        if max_checks_str:
            try:
                max_checks = int(max_checks_str)
            except ValueError:
                pass
        
        return {
            "url": url,
            "interval": interval,
            "timeout": timeout,
            "max_checks": max_checks,
            "background": background,
            "webhook_url": webhook_url if webhook_url else None,
            "webhook_payload": webhook_payload if webhook_payload else None,
            "verify_ssl": verify_ssl,
        }
    
    def validate_form(self) -> tuple[bool, dict[str, Any] | list[dict[str, Any]]]:
        """Validate form using Pydantic model.
        
        Returns (is_valid, result_or_errors).
        """
        values = self.get_form_values()
        
        try:
            validated = MonitorConfigForm(**values)
            return True, validated.model_dump()
        except ValidationError as e:
            errors = []
            for error in e.errors():
                field = error["loc"][0] if error["loc"] else "general"
                message = error["msg"]
                errors.append({"field": field, "message": message})
            return False, errors
    
    def display_errors(self, errors: list[dict[str, Any]]) -> None:
        """Display validation errors next to fields."""
        # Clear all errors first
        for field in self.query(FormField):
            field.clear_error()
        
        # Show new errors
        field_map = {
            "url": "url_input",
            "interval": "interval_input",
            "timeout": "timeout_input",
            "max_checks": "max_checks_input",
            "webhook_url": "webhook_url_input",
            "webhook_payload": "webhook_payload_input",
        }
        
        result_message = self.query_one("#result-message", Static)
        error_messages = []
        
        for error in errors:
            field_name = error["field"]
            message = error["message"]
            
            if field_name in field_map:
                # Find the form field and show error
                for field in self.query(FormField):
                    if field.input_widget.id == field_map[field_name]:
                        field.show_error(f"⚠ {message}")
                        break
            else:
                error_messages.append(f"{field_name}: {message}")
        
        if error_messages:
            result_message.update("\n".join(error_messages))
            result_message.styles.color = "red"
        else:
            result_message.update("Please fix the errors above.")
            result_message.styles.color = "red"
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "submit_btn":
            self.action_submit()
        elif event.button.id == "cancel_btn":
            self.action_cancel()
    
    def action_submit(self) -> None:
        """Submit the form."""
        is_valid, result = self.validate_form()
        
        if is_valid:
            assert isinstance(result, dict)
            self.result = result
            self.exit(result)
        else:
            assert isinstance(result, list)
            self.display_errors(result)
    
    def action_cancel(self) -> None:
        """Cancel the form."""
        self.result = None
        self.exit(None)
    
    async def action_quit(self) -> None:
        """Quit the app."""
        self.result = None
        self.exit(None)




def run_quick_check_form(defaults: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Run the quick check form and return the result.
    
    Args:
        defaults: Optional default values for form fields.
    
    Returns:
        The validated form data as a dictionary, or None if cancelled.
    """
    app = QuickCheckFormApp(defaults=defaults)
    return app.run()

class EditStep1Screen(Container):
    """Step 1: Basic Settings (interval, timeout, verify_ssl)."""
    
    def __init__(self, form_data: dict[str, Any], defaults: dict[str, Any]) -> None:
        self.form_data = form_data
        self.defaults = defaults
        super().__init__()
    
    def compose(self) -> ComposeResult:
        with Container(id="step-container"):
            yield Static("Basic Monitoring Settings", classes="step-title")
            
            interval_field = FormField(
                "Check Interval (seconds)",
                Input(
                    placeholder="60",
                    id="interval_input",
                ),
                description="Time between checks (5-86400 seconds, default: 60)",
            )
            interval_field.input_widget.value = str(
                self.form_data.get("interval") or self.defaults.get("interval") or 60
            )
            yield interval_field
            
            timeout_field = FormField(
                "HTTP Timeout (seconds)",
                Input(
                    placeholder="10",
                    id="timeout_input",
                ),
                description="Request timeout (1-300 seconds, default: 10)",
            )
            timeout_field.input_widget.value = str(
                self.form_data.get("timeout") or self.defaults.get("timeout") or 10
            )
            yield timeout_field
            
            # SSL Verification
            with Horizontal(classes="switch-row"):
                yield Label("Verify SSL Certificates:", classes="switch-label")
                yield Switch(
                    value=bool(self.form_data.get("verify_ssl") if self.form_data.get("verify_ssl") is not None else self.defaults.get("verify_ssl", True)),
                    id="verify_ssl_switch",
                )
            yield Label(
                "Disable to bypass SSL errors (e.g., self-signed certs)",
                classes="field-description",
            )
            
            with Horizontal(classes="button-row"):
                yield Button("✗ Cancel", variant="error", id="cancel_btn")
                yield Button("Next →", variant="primary", id="next_btn")
            
            yield Static("", id="step1-error")


class EditStep2Screen(Container):
    """Step 2: Webhook Settings."""
    
    def __init__(self, form_data: dict[str, Any], defaults: dict[str, Any]) -> None:
        self.form_data = form_data
        self.defaults = defaults
        super().__init__()
    
    def compose(self) -> ComposeResult:
        with Container(id="step-container"):
            yield Static("Webhook Notifications (Optional)", classes="step-title")
            
            webhook_field = FormField(
                "Webhook URL",
                Input(
                    placeholder="https://hooks.example.com/alert",
                    id="webhook_url_input",
                ),
                description="URL to POST to when checks fail (optional)",
            )
            webhook_field.input_widget.value = (
                self.form_data.get("webhook_url") or self.defaults.get("webhook_url") or ""
            )
            yield webhook_field
            
            payload_field = FormField(
                "Custom Payload (JSON)",
                Input(
                    placeholder='{"site":"{url}","error":"{error}"}',
                    id="webhook_payload_input",
                ),
                description=(
                    "Valid placeholders: {url}, {status_code}, "
                    "{error}, {timestamp}, {response_time}"
                ),
            )
            payload_field.input_widget.value = (
                self.form_data.get("webhook_payload") or self.defaults.get("webhook_payload") or ""
            )
            yield payload_field
            
            with Horizontal(classes="button-row"):
                yield Button("← Previous", variant="default", id="prev_btn")
                yield Button("✓ Save Changes", variant="success", id="submit_btn")
            
            yield Static("", id="step2-error")


class MonitorEditFormApp(App[dict[str, Any] | None]):
    """Textual app for editing monitor configuration with step-by-step wizard."""
    
    CSS = MonitorFormApp.CSS
    
    def __init__(self, defaults: dict[str, Any] | None = None) -> None:
        self.defaults = defaults or {}
        self.form_data: dict[str, Any] = self.defaults.copy()
        self.result: dict[str, Any] | None = None
        self.current_step = 1
        super().__init__()
    
    def compose(self) -> ComposeResult:
        with Container(id="wizard-container"):
            yield Static(f"Edit Monitor: {self.defaults.get('url', 'Unknown')}", id="form-title")
            
            # Step indicators
            with Horizontal(id="step-indicator-row"):
                yield StepIndicator(1, "Basic Settings", "active")
                yield StepIndicator(2, "Webhook", "pending")
            
            # Content area for steps
            yield Container(id="step-content")
            
            # Global abort button at bottom
            with Horizontal(id="abort-row"):
                yield Button("✗ Abort", variant="error", id="abort_btn")
    
    def on_mount(self) -> None:
        """Mount the first step."""
        self.show_step(1)
    
    def show_step(self, step: int) -> None:
        """Show the specified step screen."""
        self.current_step = step
        
        # Update step indicators
        indicators = self.query(StepIndicator)
        for i, indicator in enumerate(indicators, 1):
            if i < step:
                indicator.set_state("completed")
            elif i == step:
                indicator.set_state("active")
            else:
                indicator.set_state("pending")
        
        # Update content
        content = self.query_one("#step-content", Container)
        content.remove_children()
        
        if step == 1:
            content.mount(EditStep1Screen(self.form_data, self.defaults))
        elif step == 2:
            content.mount(EditStep2Screen(self.form_data, self.defaults))
    
    def collect_step_data(self, step: int) -> bool:
        """Collect data from the current step. Returns True if successful."""
        if step == 1:
            interval_str = self.query_one("#interval_input", Input).value.strip()
            timeout_str = self.query_one("#timeout_input", Input).value.strip()
            verify_ssl = self.query_one("#verify_ssl_switch", Switch).value
            
            # Parse and validate numbers
            try:
                interval = int(interval_str) if interval_str else 60
                if interval < 5 or interval > 86400:
                    raise ValueError("Interval must be between 5 and 86400")
            except ValueError as e:
                error_widget = self.query_one("#step1-error", Static)
                error_widget.update(f"⚠ Invalid interval: {e}")
                return False
            
            try:
                timeout = int(timeout_str) if timeout_str else 10
                if timeout < 1 or timeout > 300:
                    raise ValueError("Timeout must be between 1 and 300")
            except ValueError as e:
                error_widget = self.query_one("#step1-error", Static)
                error_widget.update(f"⚠ Invalid timeout: {e}")
                return False
            
            self.form_data["interval"] = interval
            self.form_data["timeout"] = timeout
            self.form_data["verify_ssl"] = verify_ssl
            return True
            
        elif step == 2:
            webhook_url = self.query_one("#webhook_url_input", Input).value.strip()
            webhook_payload = self.query_one("#webhook_payload_input", Input).value.strip()
            
            # Validate webhook URL if provided
            if webhook_url:
                if not (webhook_url.startswith("http://") or webhook_url.startswith("https://")):
                    error_widget = self.query_one("#step2-error", Static)
                    error_widget.update("⚠ Webhook URL must start with http:// or https://")
                    return False
            
            # Validate webhook payload if provided
            if webhook_payload:
                import json
                try:
                    json.loads(webhook_payload)
                except json.JSONDecodeError:
                    error_widget = self.query_one("#step2-error", Static)
                    error_widget.update("⚠ Webhook payload must be valid JSON")
                    return False
            
            self.form_data["webhook_url"] = webhook_url if webhook_url else None
            self.form_data["webhook_payload"] = webhook_payload if webhook_payload else None
            return True
        
        return False
    
    def validate_all(self) -> tuple[bool, dict[str, Any], list[dict[str, str]]]:
        """Validate all form data using Pydantic."""
        try:
            # Add URL from defaults for validation
            data_to_validate = self.form_data.copy()
            if "url" not in data_to_validate:
                data_to_validate["url"] = self.defaults.get("url", "http://placeholder.com")
            
            validated = MonitorConfigForm(**data_to_validate)
            return True, validated.model_dump(), []
        except ValidationError as e:
            errors: list[dict[str, str]] = []
            for error in e.errors():
                field = str(error["loc"][0]) if error["loc"] else "general"
                message = error["msg"]
                errors.append({"field": field, "message": message})
            return False, {}, errors
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        button_id = event.button.id
        
        if button_id == "cancel_btn":
            self.action_cancel()
        elif button_id == "next_btn":
            if self.collect_step_data(self.current_step):
                if self.current_step < 2:
                    self.show_step(self.current_step + 1)
                else:
                    self.action_submit()
        elif button_id == "prev_btn":
            # Save current data before going back
            self.collect_step_data(self.current_step)
            if self.current_step > 1:
                self.show_step(self.current_step - 1)
        elif button_id == "submit_btn":
            if self.collect_step_data(self.current_step):
                self.action_submit()
        elif button_id == "abort_btn":
            self.action_cancel()
    
    def action_submit(self) -> None:
        """Submit the form."""
        is_valid, data, errors = self.validate_all()
        
        if is_valid:
            self.result = data
            self.exit(data)
        else:
            # Show errors on current step
            error_widget = self.query_one(f"#step{self.current_step}-error", Static)
            error_messages = [f"{e['field']}: {e['message']}" for e in errors]
            error_widget.update("\n".join(error_messages))
    
    def action_cancel(self) -> None:
        """Cancel the form."""
        self.result = None
        self.exit(None)
    
    async def action_quit(self) -> None:
        """Quit the app."""
        self.result = None
        self.exit(None)


def run_edit_form(defaults: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Run the monitor edit form and return the result.
    
    Args:
        defaults: Current values for form fields.
    
    Returns:
        The validated form data as a dictionary, or None if cancelled.
    """
    app = MonitorEditFormApp(defaults=defaults)
    return app.run()
