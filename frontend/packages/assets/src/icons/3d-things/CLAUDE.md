# 3D Icon Directory — CLAUDE.md

## Directory Structure

```
3d-things/
├── animals/             (1017) Animal creatures → pet-type assets
├── art-culture/         (348)  Art & culture → luxury goods / collectibles
├── buildings/           (508)  Buildings & locations → real estate assets
├── clothing-accessories/(516)  Clothing & accessories → apparel / jewelry / bags
├── electronics/         (345)  Electronics → digital assets
├── entertainment/       (296)  Entertainment & leisure → toy-type assets
├── furniture/           (314)  Furniture & home → furniture / appliances
├── healthcare/          (256)  Healthcare & medical → other (medical devices)
├── instruments/         (120)  Musical instruments → instrument-type assets
├── kitchenware/         (230)  Kitchenware → appliances (kitchen)
├── office-stationery/   (207)  Office & stationery → other
├── plants/              (303)  Plants & flowers → other (rare plants)
├── science-tech/        (293)  Science & technology → digital (lab equipment)
├── sports/              (413)  Sports & fitness → sports-type assets
├── tools/               (450)  Tools & machinery → other (tools)
└── vehicles/            (405)  Vehicles → vehicle-type assets
```

**Total:** 16 categories, 6021 icons, ~447MB

## Thumbnail Pipeline

### Generation Command

```bash
# Run from repo root
cd frontend/apps/main
pnpm generate:thumbs
```

### Specifications

| Parameter | Value |
|-----------|-------|
| Size | 256×256 px |
| Format | WebP |
| Quality | 90 |
| Output | `public/icons/3d-thumbs/{category}/{name}.webp` |
| Total size | ~140MB (6021 files) |

### Incremental Generation

The script skips existing thumbnails. Just re-run after adding new icons.

### Original Images

```
public/icons/3d/{category}/{name}.png|webp
```

Originals are deployed via `deploy-icons.ts` script as symlinks from this directory to `public/icons/3d/`.

## Category Mapping

### System Asset Categories → 3D Icon Categories

| System Category | 3D Icon Category | Notes |
|----------------|-----------------|-------|
| Real estate | buildings | Houses, apartments, villas |
| Vehicles | vehicles | Cars, trucks, aircraft |
| Digital | electronics, science-tech | Phones, computers, lab equipment |
| Appliances | furniture, kitchenware | Furniture, kitchen appliances |
| Jewelry | clothing-accessories | Jewelry, accessories |
| Apparel | clothing-accessories | Clothing, bags |
| Beauty | clothing-accessories | Cosmetics, perfume |
| Sports | sports | Sports equipment |
| Toys | entertainment | Toys, games |
| Pets | animals | Cats, dogs, fish, birds |
| Instruments | instruments | Piano, guitar, drums |
| Bags | clothing-accessories | Handbags, suitcases |
| Luxury | art-culture, clothing-accessories | Art, collectibles |

### Naming Convention

- **Folders:** English kebab-case (e.g. `clothing-accessories`)
- **Files:** `ChineseName_English Name.ext` (e.g. `吉他音箱_Guitar Amplifier.png`)
- **Thumbnails:** `ChineseName_English Name.webp` (same name, .webp extension)

## Manifest Generation

```bash
cd frontend/apps/main
pnpm deploy:icons   # Deploy symlinks first
# Then run manually (no npm script yet)
npx tsx scripts/build-icon-manifest.ts
```

Generates `frontend/packages/assets/src/icons/icon-manifest.ts`, containing:
- 16 category definitions (id, nameZh, nameEn, folder, sortOrder, assetCategoryHints)
- 6021 icon entries (fileName, nameZh, nameEn)

## Key Decisions

### KTD-1: TypeScript manifest (not CSV)

Type-safe, IDE autocomplete, Vite tree-shaking.

### KTD-2: public directory serve (not import)

Importing 6021 files would create thousands of Vite modules. public directory files don't enter the JS bundle; URL references are naturally lazy-loaded.

### KTD-3: 256px thumbnails

- 128px is too small for detail page viewing
- 256px is clear enough for mobile detail pages (~200px display size)
- ~20KB per file, ~140MB total — acceptable

### KTD-4: 3D icons without watermarks

Preset resources, not user-created — no watermark protection needed.

## Maintenance

### Adding new icons

1. Place file in the appropriate category folder (follow `ChineseName_English Name.ext` naming)
2. Run `pnpm generate:thumbs` to generate thumbnails
3. Run `npx tsx scripts/build-icon-manifest.ts` to update manifest
4. Commit to git (via Git LFS)

### Adding new categories

1. Create English kebab-case folder
2. Update `CATEGORIES` array in `scripts/deploy-icons.ts`
3. Update `CATEGORY_DEFS` array in `scripts/build-icon-manifest.ts`
4. Update `exports` field in `frontend/packages/assets/package.json`
5. Run deploy + generate + build scripts
6. Update this CLAUDE.md's directory structure

### Removing categories

Reverse the steps above. Check for asset references to the category's icons first.

## Git LFS

All PNG/WebP files are tracked via Git LFS (`.gitattributes` already configured).

```bash
# Check LFS status
git lfs ls-files | wc -l

# Pull LFS files
git lfs pull
```
