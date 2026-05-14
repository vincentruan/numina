"""WebAuthn helper functions for passkey authentication.

Uses py_webauthn (webauthn library by Duo Labs) for credential
registration and verification.
"""

import json
from typing import Any

from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers.cose import COSEAlgorithmIdentifier
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from apps.backend.app.config import settings


def generate_registration_challenge(
    user_id: str, display_name: str, existing_credentials: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    """Generate WebAuthn registration options for a new passkey.

    Args:
        user_id: Child user UUID
        display_name: Child's display name
        existing_credentials: Already-registered credentials to exclude
            (prevents re-registering the same authenticator)

    Returns:
        Registration options dict (to be sent to client as JSON)
    """
    exclude_credentials = [
        PublicKeyCredentialDescriptor(id=bytes.fromhex(cred["id"]))
        for cred in (existing_credentials or [])
    ]
    options = generate_registration_options(
        rp_id=settings.WEBAUTHN_RP_ID,
        rp_name=settings.WEBAUTHN_RP_NAME,
        user_id=user_id.encode("utf-8"),
        user_name=display_name,
        user_display_name=display_name,
        exclude_credentials=exclude_credentials,
        authenticator_selection=AuthenticatorSelectionCriteria(
            user_verification=UserVerificationRequirement.REQUIRED,
            resident_key=ResidentKeyRequirement.PREFERRED,
        ),
        supported_pub_key_algs=[
            COSEAlgorithmIdentifier.ECDSA_SHA_256,
            COSEAlgorithmIdentifier.RSASSA_PKCS1_v1_5_SHA_256,
        ],
    )
    return json.loads(options_to_json(options))


def verify_registration(
    credential: dict[str, Any],
    expected_challenge: bytes,
) -> dict[str, Any]:
    """Verify WebAuthn registration response from client.

    Returns:
        Verified credential dict with id, public_key, sign_count

    Raises:
        Exception: If verification fails
    """
    verification = verify_registration_response(
        credential=credential,
        expected_challenge=expected_challenge,
        expected_origin=settings.WEBAUTHN_ORIGIN,
        expected_rp_id=settings.WEBAUTHN_RP_ID,
    )
    return {
        "id": verification.credential_id.hex(),
        "public_key": verification.credential_public_key.hex(),
        "sign_count": verification.sign_count,
    }


def generate_authentication_challenge(
    allowed_credentials: list[dict[str, Any]],
) -> dict[str, Any]:
    """Generate WebAuthn authentication options.

    Args:
        allowed_credentials: List of stored credentials
            [{"id": "hex_string", "public_key": "hex_string", "sign_count": 0}]

    Returns:
        Authentication options dict (to be sent to client as JSON)
    """
    descriptors = [
        PublicKeyCredentialDescriptor(id=bytes.fromhex(cred["id"]))
        for cred in allowed_credentials
    ]
    options = generate_authentication_options(
        rp_id=settings.WEBAUTHN_RP_ID,
        allow_credentials=descriptors,
        user_verification=UserVerificationRequirement.REQUIRED,
    )
    return json.loads(options_to_json(options))


def verify_authentication(
    credential: dict[str, Any],
    expected_challenge: bytes,
    credential_public_key: bytes,
    credential_current_sign_count: int,
) -> dict[str, Any]:
    """Verify WebAuthn authentication response from client.

    Returns:
        Dict with new_sign_count

    Raises:
        Exception: If verification fails
    """
    verification = verify_authentication_response(
        credential=credential,
        expected_challenge=expected_challenge,
        expected_origin=settings.WEBAUTHN_ORIGIN,
        expected_rp_id=settings.WEBAUTHN_RP_ID,
        credential_public_key=credential_public_key,
        credential_current_sign_count=credential_current_sign_count,
    )
    return {
        "new_sign_count": verification.new_sign_count,
    }
