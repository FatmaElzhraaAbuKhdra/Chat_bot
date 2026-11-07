-- ============================================================
-- APEX SSO Setup for JustClick AI Chatbot
-- Run as the application schema owner (JC or similar)
-- ============================================================

-- 1) Tables
-- ============================================================

CREATE TABLE chatbot_user_roles (
  app_user   VARCHAR2(255) PRIMARY KEY,
  role_name  VARCHAR2(30)  NOT NULL
             CHECK (role_name IN ('admin','manager','accountant','sales','warehouse','hr','viewer')),
  branches   VARCHAR2(500),   -- e.g. "5,6" for branch-restricted roles; NULL = all branches
  is_active  NUMBER(1) DEFAULT 1 NOT NULL
);

-- Secret table: only the package owner should have access — grant NO privileges on it
CREATE TABLE chatbot_sso_config (secret VARCHAR2(200) NOT NULL);

-- 2) Seed the secret  (same value as JWT_SECRET in .env on the server)
-- Replace the value below with the output of:  openssl rand -base64 48
INSERT INTO chatbot_sso_config VALUES ('LfqGp1aci4julBuB5Jpalrcei4XGP2nZT9CaOzu6XvW_usO3BBKPdItjfUQa2vnA');
COMMIT;

-- 3) Seed user roles  (add all staff who should access the chatbot)
-- INSERT INTO chatbot_user_roles (app_user, role_name) VALUES ('AHMED',  'sales');
-- INSERT INTO chatbot_user_roles (app_user, role_name) VALUES ('OMAR',   'warehouse');
-- INSERT INTO chatbot_user_roles (app_user, role_name) VALUES ('FATMA',  'manager');
-- INSERT INTO chatbot_user_roles (app_user, role_name) VALUES ('ADMIN',  'admin');
-- COMMIT;

-- 4) PL/SQL package  (signs HS256 JWT tokens)
-- ============================================================

CREATE OR REPLACE PACKAGE chatbot_sso AS
  -- Returns a signed JWT for the given APEX user; NULL if no active role found
  FUNCTION token_for (p_app_user IN VARCHAR2, p_ttl_seconds IN NUMBER DEFAULT 600)
    RETURN VARCHAR2;
END chatbot_sso;
/

CREATE OR REPLACE PACKAGE BODY chatbot_sso AS

  FUNCTION b64url (p_raw IN RAW) RETURN VARCHAR2 IS
    l_txt VARCHAR2(32767);
  BEGIN
    l_txt := UTL_RAW.CAST_TO_VARCHAR2(UTL_ENCODE.BASE64_ENCODE(p_raw));
    -- BASE64_ENCODE inserts CR/LF line breaks — remove them
    l_txt := REPLACE(REPLACE(l_txt, CHR(13)), CHR(10));
    -- Convert standard Base64 to URL-safe Base64 and strip padding
    RETURN RTRIM(TRANSLATE(l_txt, '+/', '-_'), '=');
  END b64url;

  FUNCTION utf8 (p_text IN VARCHAR2) RETURN RAW IS
  BEGIN
    RETURN UTL_I18N.STRING_TO_RAW(p_text, 'AL32UTF8');
  END utf8;

  FUNCTION epoch_now RETURN NUMBER IS
  BEGIN
    RETURN TRUNC(
      (CAST(SYS_EXTRACT_UTC(SYSTIMESTAMP) AS DATE) - DATE '1970-01-01') * 86400
    );
  END epoch_now;

  FUNCTION token_for (p_app_user IN VARCHAR2, p_ttl_seconds IN NUMBER DEFAULT 600)
    RETURN VARCHAR2
  IS
    l_role      chatbot_user_roles.role_name%TYPE;
    l_branches  chatbot_user_roles.branches%TYPE;
    l_secret    chatbot_sso_config.secret%TYPE;
    l_branch_js VARCHAR2(1000) := '[]';
    l_now       NUMBER := epoch_now;
    l_header    VARCHAR2(100)  := '{"alg":"HS256","typ":"JWT"}';
    l_payload   VARCHAR2(4000);
    l_signing   VARCHAR2(5000);
  BEGIN
    -- Lookup active role for this APEX user
    BEGIN
      SELECT role_name, branches
        INTO l_role, l_branches
        FROM chatbot_user_roles
       WHERE app_user = UPPER(p_app_user) AND is_active = 1;
    EXCEPTION
      WHEN NO_DATA_FOUND THEN RETURN NULL;   -- no role = no access
    END;

    -- Read signing secret
    SELECT secret INTO l_secret FROM chatbot_sso_config;

    -- Build branches JSON array
    IF l_branches IS NOT NULL THEN
      SELECT '[' ||
             LISTAGG('"' || TRIM(COLUMN_VALUE) || '"', ',')
               WITHIN GROUP (ORDER BY ROWNUM) ||
             ']'
        INTO l_branch_js
        FROM TABLE(apex_string.split(l_branches, ','));
    END IF;

    -- Build payload
    SELECT JSON_OBJECT(
             'sub'      VALUE UPPER(p_app_user),
             'role'     VALUE l_role,
             'branches' VALUE l_branch_js FORMAT JSON,
             'iat'      VALUE l_now,
             'exp'      VALUE l_now + p_ttl_seconds
           )
      INTO l_payload
      FROM DUAL;

    -- Sign: header.payload  then HMAC-SHA256
    l_signing := b64url(utf8(l_header)) || '.' || b64url(utf8(l_payload));
    RETURN l_signing || '.' ||
           b64url(DBMS_CRYPTO.MAC(
             utf8(l_signing),
             DBMS_CRYPTO.HMAC_SH256,
             utf8(l_secret)
           ));
  END token_for;

END chatbot_sso;
/

-- 5) Quick smoke test (run after seeding chatbot_user_roles)
-- SELECT chatbot_sso.token_for('AHMED') FROM dual;
-- Should return a long string like:  eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJBSE1FRC...
