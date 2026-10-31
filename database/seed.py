"""Add explicitly fictional sample data to an existing workspace."""
import argparse
from pathlib import Path
import sys
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'backend'),str(Path(__file__).resolve().parents[1])]
from sqlalchemy import select
from core.database import session_scope
from models.entities import User, Organization, Membership
from database.seeds.demo import seed_workspace
parser=argparse.ArgumentParser()
parser.add_argument('--organization',required=True)
parser.add_argument('--user',required=True)
args=parser.parse_args()
with session_scope() as db:
    user=db.get(User,args.user);org=db.get(Organization,args.organization)
    member=db.scalar(select(Membership).where(Membership.user_id==args.user,Membership.organization_id==args.organization)) if user and org else None
    if not member: raise SystemExit('The user must be a member of the organization.')
    if not org.is_demo: raise SystemExit('Sample seeding is restricted to demo organizations so fictional data is never mixed into a real workspace. Open /demo to create one.')
    seed_workspace(db,org,user)
    print('Sample data is ready. It is fictional and requires no external connections.')
