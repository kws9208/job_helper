from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from config.setting import Setting

def get_engine():
    connect_args = {}

    if Setting.WALLET_DIR:
        connect_args = {
            "config_dir": Setting.WALLET_DIR,
            "wallet_location": Setting.WALLET_DIR,
            "wallet_password": Setting.WALLET_PASSWORD
        }

    db_url = f"oracle+oracledb://{Setting.ORACLE_USER}:{Setting.ORACLE_PASSWORD}@{Setting.ORACLE_DSN}"
    
    engine = create_engine(
        db_url, 
        connect_args=connect_args,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True
    )
    
    return engine

def get_session_factory():
    engine = get_engine()
    return sessionmaker(bind=engine, expire_on_commit=False)

if __name__ == "__main__":
    try:
        engine = get_engine()
        with engine.connect() as connection:
            connection.execute(text("SELECT 1 FROM DUAL"))
            print("✅ 1단계: 엔진(Connection) 연결 성공!")
    except Exception as e:
        print(f"❌ 1단계 실패: {e}")
        exit(1)

    print("\n--- 2단계: 세션(Session) 생성 테스트 ---")
    
    SessionFactory = get_session_factory()
    session = SessionFactory()

    try:
        result = session.execute(text("SELECT 1 FROM DUAL"))
        value = result.scalar()
        
        print(f"✅ 2단계: 세션 동작 성공! (응답값: {value})")
        print("🎉 이제 Repository에서 DB를 사용할 준비가 완료되었습니다.")

    except Exception as e:
        print(f"❌ 2단계 실패: 세션을 만드는 중 에러가 났습니다.\n{e}")
        
    finally:
        session.close()
        print("🔌 세션 종료 (반납 완료)")