from database import Base
from sqlalchemy import Column, Integer, String, Boolean

class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Integer, default=False) 

    def __repr__(self):
        return f"<User(id={self.id}, username={self.username}, is_active={self.is_active}, is_superuser={self.is_superuser})>"