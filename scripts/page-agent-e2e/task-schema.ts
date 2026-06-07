import { z } from 'zod';
import { readFileSync, readdirSync } from 'fs';
import { parse as parseYaml } from 'yaml';
import { resolve, dirname, join } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));

const AssertionSchema = z.object({
  type: z.enum([
    'url_contains',
    'url_equals',
    'text_visible',
    'text_not_visible',
    'locator_visible',
    'locator_count',
    'console_no_errors',
    'network_no_failures',
  ]),
  value: z.string().optional(),
  selector: z.string().optional(),
  count: z.number().optional(),
  timeoutMs: z.number().optional(),
}).superRefine((data, ctx) => {
  const needsValue = ['url_contains', 'url_equals', 'text_visible', 'text_not_visible'];
  if (needsValue.includes(data.type) && !data.value) {
    ctx.addIssue({ code: z.ZodIssueCode.custom, message: `'value' is required for assertion type '${data.type}'`, path: ['value'] });
  }
  const needsSelector = ['locator_visible', 'locator_count'];
  if (needsSelector.includes(data.type) && !data.selector) {
    ctx.addIssue({ code: z.ZodIssueCode.custom, message: `'selector' is required for assertion type '${data.type}'`, path: ['selector'] });
  }
  if (data.type === 'locator_count' && data.count === undefined) {
    ctx.addIssue({ code: z.ZodIssueCode.custom, message: `'count' is required for assertion type 'locator_count'`, path: ['count'] });
  }
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
  const parsed = parseYaml(content, { maxAliasCount: 100 });
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
    let filePaths: string[];
    if (resolved.includes('*')) {
      // Simple glob: find .yaml files recursively in the parent directory
      const baseDir = resolved.substring(0, resolved.indexOf('*'));
      filePaths = [];
      const walkDir = (dir: string) => {
        try {
          for (const entry of readdirSync(dir, { withFileTypes: true })) {
            const full = join(dir, entry.name);
            if (entry.isDirectory()) walkDir(full);
            else if (entry.name.endsWith('.yaml') || entry.name.endsWith('.yml')) filePaths.push(full);
          }
        } catch { /* directory doesn't exist */ }
      };
      walkDir(baseDir);
    } else {
      filePaths = [resolved];
    }

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
