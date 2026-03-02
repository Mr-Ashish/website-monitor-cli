"""Pydantic models for form validation and data validation.

Provides structured validation for monitor configuration inputs
with clear error messages for users.
"""

from typing import Self

from pydantic import BaseModel, Field, field_validator, model_validator


class MonitorConfigForm(BaseModel):
    """Form model for creating a new monitor configuration.
    
    Validates user input with helpful error messages for the TUI form.
    """
    
    url: str = Field(
        ...,
        description="The website URL to monitor (must be valid http/https)",
        examples=["https://example.com", "http://localhost:8080"],
    )
    interval: int = Field(
        default=60,
        ge=5,
        le=86400,
        description="Check interval in seconds (5-86400)",
    )
    timeout: int = Field(
        default=10,
        ge=1,
        le=300,
        description="HTTP timeout in seconds (1-300)",
    )
    max_checks: int | None = Field(
        default=None,
        ge=1,
        le=10000,
        description="Maximum checks before stopping (unlimited if empty)",
    )
    background: bool = Field(
        default=False,
        description="Run as background daemon job",
    )
    webhook_url: str | None = Field(
        default=None,
        description="Webhook URL to notify on failure (optional)",
    )
    webhook_payload: str | None = Field(
        default=None,
        description="Custom JSON payload template for webhook (optional)",
    )
    verify_ssl: bool = Field(
        default=True,
        description="Verify SSL certificates for HTTPS requests",
    )
    
    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Validate that URL is well-formed HTTP/HTTPS."""
        v = v.strip()
        if not v:
            raise ValueError("URL is required")
        
        # Basic URL validation
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("URL must start with http:// or https://")
        
        # Check for minimal valid URL structure
        try:
            from urllib.parse import urlparse
            result = urlparse(v)
            if not result.netloc:
                raise ValueError("URL must have a valid domain (e.g., example.com)")
        except Exception as e:
            raise ValueError(f"Invalid URL format: {e}")
        
        return v
    
    @field_validator("webhook_url")
    @classmethod
    def validate_webhook_url(cls, v: str | None) -> str | None:
        """Validate webhook URL if provided."""
        if v is None or v == "":
            return None
        
        v = v.strip()
        if not v:
            return None
            
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("Webhook URL must start with http:// or https://")
        
        return v
    
    @field_validator("webhook_payload")
    @classmethod
    def validate_webhook_payload(cls, v: str | None) -> str | None:
        """Validate webhook payload template if provided."""
        if v is None or v == "":
            return None
        
        v = v.strip()
        if not v:
            return None
        
        # Check for valid JSON structure (basic check)
        import json
        try:
            # Try to parse as JSON (will fail if invalid)
            json.loads(v)
        except json.JSONDecodeError:
            raise ValueError("Webhook payload must be valid JSON")
        
        # Check for valid placeholders
        valid_placeholders = {"{url}", "{status_code}", "{error}", "{timestamp}", "{response_time}"}
        import re
        # Find all placeholders in the string
        placeholders = set(re.findall(r"\{[^}]+\}", v))
        invalid = placeholders - valid_placeholders
        if invalid:
            raise ValueError(
                f"Invalid placeholders: {', '.join(invalid)}. "
                f"Valid: {', '.join(valid_placeholders)}"
            )
        
        return v
    
    @model_validator(mode="after")
    def validate_consistency(self) -> Self:
        """Validate cross-field consistency."""
        # If webhook_payload is set, webhook_url must also be set
        if self.webhook_payload and not self.webhook_url:
            raise ValueError("Webhook payload requires a webhook URL to be set")
        
        # Timeout should not exceed interval (warn but allow)
        if self.timeout > self.interval:
            # This is a warning scenario but we'll allow it
            # The UI can display a warning
            pass
        
        return self


class QuickCheckForm(BaseModel):
    """Form model for quick single URL check.
    
    Simplified form for one-time checks.
    """
    
    url: str = Field(
        ...,
        description="The website URL to check",
    )
    timeout: int = Field(
        default=10,
        ge=1,
        le=300,
        description="HTTP timeout in seconds (1-300)",
    )
    verify_ssl: bool = Field(
        default=True,
        description="Verify SSL certificates",
    )
    
    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Validate that URL is well-formed HTTP/HTTPS."""
        v = v.strip()
        if not v:
            raise ValueError("URL is required")
        
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("URL must start with http:// or https://")
        
        try:
            from urllib.parse import urlparse
            result = urlparse(v)
            if not result.netloc:
                raise ValueError("URL must have a valid domain")
        except Exception as e:
            raise ValueError(f"Invalid URL format: {e}")
        
        return v


class JobUpdateForm(BaseModel):
    """Form model for updating an existing job's configuration."""
    
    interval: int | None = Field(
        default=None,
        ge=5,
        le=86400,
        description="New check interval in seconds",
    )
    timeout: int | None = Field(
        default=None,
        ge=1,
        le=300,
        description="New HTTP timeout in seconds",
    )
    webhook_url: str | None = Field(
        default=None,
        description="New webhook URL (empty to clear)",
    )
    webhook_payload: str | None = Field(
        default=None,
        description="New webhook payload template (empty to clear)",
    )
    verify_ssl: bool | None = Field(
        default=None,
        description="Enable/disable SSL verification",
    )
    
    @field_validator("webhook_url")
    @classmethod
    def validate_webhook_url(cls, v: str | None) -> str | None:
        """Validate webhook URL if provided."""
        if v is None or v == "":
            return None
        
        v = v.strip()
        if not v:
            return None
            
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("Webhook URL must start with http:// or https://")
        
        return v
    
    @field_validator("webhook_payload")
    @classmethod
    def validate_webhook_payload(cls, v: str | None) -> str | None:
        """Validate webhook payload template if provided."""
        if v is None or v == "":
            return None
        
        v = v.strip()
        if not v:
            return None
        
        import json
        try:
            json.loads(v)
        except json.JSONDecodeError:
            raise ValueError("Webhook payload must be valid JSON")
        
        return v
    
    @model_validator(mode="after")
    def validate_at_least_one_field(self) -> Self:
        """Ensure at least one field is being updated."""
        fields_to_check = [
            self.interval,
            self.timeout,
            self.webhook_url,
            self.webhook_payload,
            self.verify_ssl,
        ]
        if all(v is None for v in fields_to_check):
            raise ValueError("At least one field must be provided for update")
        return self