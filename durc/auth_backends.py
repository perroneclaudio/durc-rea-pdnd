from django.contrib.auth import get_user_model
from django_auth_ldap.backend import LDAPBackend


class SelectiveLDAPBackend(LDAPBackend):
    """
    Autentica tramite LDAP solo utenti già presenti in Django
    e privi di una password locale utilizzabile.

    In questo modo la presenza o meno della password locale
    determina esplicitamente il metodo di autenticazione:
    - password locale utilizzabile -> autenticazione LOCAL;
    - password locale non utilizzabile -> autenticazione LDAP.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or not password:
            return None

        UserModel = get_user_model()

        try:
            user = UserModel._default_manager.get(
                username__iexact=username
            )
        except UserModel.DoesNotExist:
            return None

        if user.has_usable_password():
            return None

        return super().authenticate(
            request,
            username=user.get_username(),
            password=password,
            **kwargs,
        )
