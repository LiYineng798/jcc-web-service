from app import create_app

app = create_app()

if __name__ == '__main__':
    with app.app_context():
        from db import init_db
        init_db()
    print('数据库迁移完成')
