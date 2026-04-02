## ADDED Requirements

### Requirement: 登录响应时间必须恒定

系统 SHALL 确保登录失败时响应时间一致，无论用户是否存在。当用户不存在时，执行 dummy bcrypt 验证以消耗相同时间。

#### Scenario: 用户不存在时响应时间

- **WHEN** 登录用户名不存在
- **THEN** 系统执行 dummy bcrypt 验证，响应时间约 200-300ms

#### Scenario: 用户存在密码错误时响应时间

- **WHEN** 登录用户名存在但密码错误
- **THEN** 系统执行 bcrypt 验证，响应时间约 200-300ms

#### Scenario: 响应时间一致性验证

- **WHEN** 多次测试用户不存在和密码错误两种情况
- **THEN** 平均响应时间差异小于 20%

### Requirement: bcrypt rounds 必须可配置

系统 SHALL 在 `config.py` 中定义 `BCRYPT_ROUNDS` 配置项（默认 12）。

#### Scenario: 配置 bcrypt rounds

- **WHEN** 配置 `BCRYPT_ROUNDS=14`
- **THEN** 密码哈希使用 14 rounds

#### Scenario: rounds 影响哈希时间

- **WHEN** 使用 higher rounds（如 14）
- **THEN** 哈希时间增加（约 250ms），安全强度提升

### Requirement: 密码哈希必须使用配置的 rounds

系统 SHALL 在 `hash_password()` 中使用 `settings.BCRYPT_ROUNDS` 生成 salt。

#### Scenario: 生成密码哈希

- **WHEN** 调用 `hash_password("password")`
- **THEN** bcrypt 哈希格式为 `$2b$XX$...`，其中 XX 为配置的 rounds

### Requirement: 登录失败必须不区分错误原因

系统 SHALL 对所有登录失败返回相同的错误信息 "用户名或密码错误"，不提示具体原因。

#### Scenario: 用户不存在错误信息

- **WHEN** 登录用户名不存在
- **THEN** 返回 401 状态码，提示 "用户名或密码错误"

#### Scenario: 密码错误信息

- **WHEN** 登录密码错误
- **THEN** 返回 401 状态码，提示 "用户名或密码错误"