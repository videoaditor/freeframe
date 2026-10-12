"""Synthetic local fixture using the verified existing Alan identity and staff scope.

Run only inside autoreview-h4-api-1. No production credentials or media are copied.
"""
import uuid
from apps.api.config import settings
from apps.api.database import SessionLocal
from apps.api.models.user import User, UserStatus
from apps.api.models.project import Project, ProjectType
from apps.api.services.auth_service import hash_password
from apps.api.services.s3_service import get_s3_client

assert settings.database_url == 'postgresql://h4:h4@postgres:5432/h4'
db = SessionLocal()
alan_id = uuid.UUID('5f026c71-d1a8-4dde-89dc-c2d36a948066')
admin_id = uuid.UUID('4e33e724-fb69-418a-9951-c12e164d2cfb')
project_id = uuid.UUID('0f353bd9-c353-4cfd-97d9-2997afb47feb')
for user_id, email, name, admin in [(alan_id, 'alan@aditor.ai', 'Alan · local fixture', False), (admin_id, 'system@h4.invalid', 'Existing system identity · sanitized', True)]:
    if not db.get(User, user_id):
        db.add(User(id=user_id, email=email, name=name, status=UserStatus.active,
                    is_superadmin=admin, is_staff=True, email_verified=True,
                    password_hash=hash_password('h4-isolated-fixture')))
db.flush()
if not db.get(Project, project_id):
    db.add(Project(id=project_id, name='H4 Brand', created_by=alan_id,
                   project_type=ProjectType.team, is_workspace=True))
db.commit()
get_s3_client().put_bucket_cors(Bucket=settings.s3_bucket, CORSConfiguration={'CORSRules':[{
    'AllowedOrigins':['http://localhost:13044'], 'AllowedMethods':['GET','PUT','POST','HEAD'],
    'AllowedHeaders':['*'], 'ExposeHeaders':['ETag'], 'MaxAgeSeconds':3600,
}]})
print('H4_LOCAL_FIXTURE_READY; existing identity IDs, synthetic password/content; production unchanged')
