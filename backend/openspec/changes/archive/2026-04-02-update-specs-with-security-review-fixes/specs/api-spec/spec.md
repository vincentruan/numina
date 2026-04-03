## MODIFIED Requirements

### Requirement: bcrypt rounds 必须可配置

系统 SHALL 在 `config.py` 中定义 `BCRYPT_ROUNDS` 配置项（默认 12）。该配置项适用于所有密码哈希场景，包括：
- 用户注册时的密码哈希
- 用户修改密码时的密码哈希
- 时间攻击防护中的 dummy hash

#### Scenario: 配置 bcrypt rounds

- **WHEN** 配置 `BCRYPT_ROUNDS=14`
- **THEN** 所有密码哈希操作使用 14 rounds

#### Scenario: rounds 影响哈希时间

- **WHEN** 使用 higher rounds（如 14）
- **THEN** 哈希时间增加（约 250ms），安全强度提升

#### Scenario: 时间攻击防护使用配置的 rounds

- **WHEN** 登录用户名不存在时执行 dummy hash
- **THEN** dummy hash 使用 `settings.BCRYPT_ROUNDS` 配置，确保与正常验证时间一致