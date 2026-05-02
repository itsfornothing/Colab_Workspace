import logging
from django.core.management.base import BaseCommand
from django.utils import timezone
 
logger = logging.getLogger(__name__)
 
 
class Command(BaseCommand):
    help = "Prune expired auth tokens, sessions, and verification records"
 
    def handle(self, *args, **options):
        now = timezone.now()
 
        from app.models import (
            TokenBlacklist, UserSession,
            PasswordResetToken, EmailVerification,
        )
 
        bl = TokenBlacklist.objects.filter(expires_at__lt=now).delete()
        self.stdout.write(f"TokenBlacklist: deleted {bl[0]} expired entries")
 
        sess = UserSession.objects.filter(expires_at__lt=now).delete()
        self.stdout.write(f"UserSession: deleted {sess[0]} expired sessions")
 
        prt = PasswordResetToken.objects.filter(
            expires_at__lt=now
        ).delete()
        self.stdout.write(f"PasswordResetToken: deleted {prt[0]} expired tokens")
 
        ev = EmailVerification.objects.filter(
            expires_at__lt=now
        ).delete()
        self.stdout.write(f"EmailVerification: deleted {ev[0]} expired records")
 
        logger.info(
            "cleanup_tokens: bl=%d sess=%d prt=%d ev=%d",
            bl[0], sess[0], prt[0], ev[0],
        )
        self.stdout.write(self.style.SUCCESS("Token cleanup complete"))