CREATE TABLE IF NOT EXISTS user_access (
    user_id INTEGER NOT NULL PRIMARY KEY,
    permissions JSON NOT NULL,
    CONSTRAINT fk_user_access_user
        FOREIGN KEY (user_id) REFERENCES users (id)
        ON DELETE CASCADE
);
