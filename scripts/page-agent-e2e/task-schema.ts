import { z } from 'zod';
import { readFileSync } from 'fs';
import { parse as parseYaml } from 'yaml';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';
import { globSync } from 'node:fs';

const __dirname = dirname(fileURLToPath(import.meta.url));

const AssertionSchema = z.object({
  type: z.enum([
    'url_contains',
    'url_equals',
    'text_visible',
    'text_not_visible',
    'locator_visible',
    'locator_count',
    'api_response',
    'db_query',
    'log_contains',
    'console_no_errors',
    'network_no_failures',
  ]),
  value: z.string().optional(),
  selector: z.string().optional(),
  count: z.number().optional(),
  timeoutMs: z.number().optional(),
  query: z.string().optional(),
  expected: z.string().optional(),
});

const FixturesSchema = z.object({
  seed: z.string().optional(),
  user: z.string().optional(),
  role: z.string().optional(),
}).optional();

const CaseSchema = z.object({
  id: z.string().min(1),
  app: z.enum(['main', 'child']).optional().default('main'),
  description: z.string().optional(),
  baseUrl: z.string().url().optional(),
  route: z.string().min(1),
  task: z.string().min(1),
  maxSteps: z.number().int().min(1).max(100).default(20),
  timeoutMs: z.number().int().min(1000).optional().default(30000),
  storageState: z.string().optional(),
  tags: z.array(z.string()).optional(),
  fixtures: FixturesSchema,
  assertions: z.array(AssertionSchema).min(1),
});

const TaskFileSchema = z.object({
  cases: z.array(CaseSchema).min(1),
});

export type TaskCase = z.infer<typeof CaseSchema>;
export type TaskFile = z.infer<typeof TaskFileSchema>;
export type Assertion = z.infer<typeof AssertionSchema>;

export function validateTaskFile(filePath: string): TaskFile {
  const content = readFileSync(filePath, 'utf-8');
  const parsed = parseYaml(content);
  return TaskFileSchema.parse(parsed);
}

export function validateTaskFileWithErrors(filePath: string): { success: boolean; data?: TaskFile; errors?: string[] } {
  try {
    const data = validateTaskFile(filePath);
    return { success: true, data };
  } catch (err) {
    if (err instanceof z.ZodError) {
      const errors = err.errors.map(
        (e) => `  ${e.path.join('.')}: ${e.message}`
      );
      return { success: false, errors };
    }
    return { success: false, errors: [(err as Error).message] };
  }
}

// CLI mode: tsx task-schema.ts --validate <file-or-glob>...
if (process.argv.includes('--validate')) {
  const patterns = process.argv.slice(process.argv.indexOf('--validate') + 1);
  if (patterns.length === 0) {
    console.error('Usage: tsx task-schema.ts --validate <file-or-glob>...');
    process.exit(1);
  }

  let hasError = false;
  const projectRoot = resolve(__dirname, '../..');

  for (const pattern of patterns) {
    const resolved = resolve(pattern);
    const filePaths = resolved.includes('*') ? globSync(resolved) : [resolved];

    for (const filePath of filePaths) {
      const relative = filePath.replace(projectRoot + '/', '');
      const result = validateTaskFileWithErrors(filePath);
      if (result.success) {
        const caseCount = result.data!.cases.length;
        console.log(`✓ ${relative} (${caseCount} cases)`);
      } else {
        console.error(`✗ ${relative}`);
        result.errors!.forEach((e) => console.error(e));
        hasError = true;
      }
    }
  }

  process.exit(hasError ? 1 : 0);
}
