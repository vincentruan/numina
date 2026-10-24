#!/usr/bin/env python3
"""One-time audit script for os-taxonomy-beijing knowledge graph data quality.

Analyzes topics.json, dependencies.json, and clusters.json to produce
a data quality report covering:
- Subject distribution
- Orphan nodes (no incoming AND no outgoing edges)
- Circular dependencies
- Broken links (references to non-existent topic IDs)
- Cluster coverage
- Age range statistics
"""

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path


def load_data(base_dir: Path) -> tuple[list, list, list]:
    topics_file = base_dir / "topics.json"
    deps_file = base_dir / "dependencies.json"
    clusters_file = base_dir / "clusters.json"

    with open(topics_file, encoding="utf-8") as f:
        topics_data = json.load(f)
    with open(deps_file, encoding="utf-8") as f:
        deps_data = json.load(f)
    with open(clusters_file, encoding="utf-8") as f:
        clusters_data = json.load(f)

    return topics_data["topics"], deps_data["dependencies"], clusters_data["clusters"]


def find_orphan_nodes(topics: list, deps: list) -> list[str]:
    """Topics with no incoming AND no outgoing edges."""
    topic_ids = {t["id"] for t in topics}
    has_edge = set()
    for d in deps:
        has_edge.add(d["topicId"])
        has_edge.add(d["prerequisiteId"])
    orphans = sorted(topic_ids - has_edge)
    return orphans


def find_broken_links(topics: list, deps: list) -> list[dict]:
    """Dependencies referencing non-existent topic IDs."""
    topic_ids = {t["id"] for t in topics}
    broken = []
    for d in deps:
        if d["topicId"] not in topic_ids:
            broken.append({"edge": "topicId", "value": d["topicId"], "dep": d})
        if d["prerequisiteId"] not in topic_ids:
            broken.append({"edge": "prerequisiteId", "value": d["prerequisiteId"], "dep": d})
    return broken


def detect_cycles(topics: list, deps: list) -> list[list[str]]:
    """Detect circular dependencies using DFS. Returns list of cycles found."""
    # Build adjacency list: topic -> prerequisites (directed edges)
    adj = defaultdict(set)
    for d in deps:
        adj[d["topicId"]].add(d["prerequisiteId"])

    topic_ids = {t["id"] for t in topics}
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {tid: WHITE for tid in topic_ids}
    cycles = []

    def dfs(node, path):
        color[node] = GRAY
        for neighbor in adj.get(node, set()):
            if neighbor not in topic_ids:
                continue  # broken link, handled elsewhere
            if color[neighbor] == GRAY:
                # Found a cycle - extract it
                cycle_start = neighbor
                cycle = []
                # Walk back through path to find the cycle
                idx = len(path) - 1
                while idx >= 0 and path[idx] != cycle_start:
                    cycle.append(path[idx])
                    idx -= 1
                cycle.append(cycle_start)
                cycle.reverse()
                cycles.append(cycle)
            elif color[neighbor] == WHITE:
                dfs(neighbor, path + [neighbor])
        color[node] = BLACK

    for tid in topic_ids:
        if color[tid] == WHITE:
            dfs(tid, [tid])

    return cycles


def analyze_age_ranges(topics: list) -> dict:
    """Analyze age range coverage per subject."""
    by_subject = defaultdict(list)
    for t in topics:
        by_subject[t["subject"]].append((t.get("ageRangeStart"), t.get("ageRangeEnd")))

    result = {}
    for subject, ranges in sorted(by_subject.items()):
        starts = [r[0] for r in ranges if r[0] is not None]
        ends = [r[1] for r in ranges if r[1] is not None]
        result[subject] = {
            "count": len(ranges),
            "min_age": min(starts) if starts else None,
            "max_age": max(ends) if ends else None,
            "no_age_range": sum(1 for s, e in ranges if s is None or e is None),
        }
    return result


def analyze_clusters(clusters: list, topics: list) -> dict:
    """Analyze cluster coverage vs topics."""
    # Group topics by (subject, domain)
    topic_domains = Counter()
    for t in topics:
        topic_domains[(t["subject"], t["domain"])] += 1

    cluster_domains = {(c["subject"], c["domain"]) for c in clusters}

    covered = topic_domains.keys() & cluster_domains
    uncovered = set(topic_domains.keys()) - cluster_domains

    return {
        "total_clusters": len(clusters),
        "total_domains": len(topic_domains),
        "domains_with_clusters": len(covered),
        "domains_without_clusters": len(uncovered),
        "uncovered_domains": sorted(
            [{"subject": s, "domain": d, "topic_count": topic_domains[(s, d)]} for s, d in uncovered],
            key=lambda x: -x["topic_count"],
        ),
    }


def analyze_translation_coverage(topics: list) -> dict:
    """Check which fields have Chinese translations."""
    zh_fields = ["nameZh", "descriptionZh", "evidenceZh", "assessmentPromptZh"]
    stats = {f: 0 for f in zh_fields}
    for t in topics:
        for f in zh_fields:
            if t.get(f):
                stats[f] += 1
    total = len(topics)
    return {
        field: {"count": count, "rate": count / total if total else 0}
        for field, count in stats.items()
    }


def analyze_strength_distribution(deps: list) -> dict:
    """Analyze dependency strength distribution."""
    return dict(Counter(d.get("strength", "unknown") for d in deps))


def generate_report(base_dir: Path) -> str:
    topics, deps, clusters = load_data(base_dir)
    topic_ids = {t["id"] for t in topics}

    lines = []
    lines.append("# 知识图谱数据质量报告 (os-taxonomy-beijing)")
    lines.append("")
    lines.append(f"> **生成日期**: 2026-10-12")
    lines.append(f"> **数据版本**: v1")
    lines.append(f"> **数据源**: `server/packages/os_taxonomy/`")
    lines.append("")
    lines.append("## 1. 总体统计")
    lines.append("")
    lines.append(f"| 指标 | 数量 |")
    lines.append(f"|------|------|")
    lines.append(f"| 知识点 (topics) | {len(topics)} |")
    lines.append(f"| 先修关系 (dependencies) | {len(deps)} |")
    lines.append(f"| 聚类 (clusters) | {len(clusters)} |")
    lines.append(f"| 唯一 topic IDs | {len(topic_ids)} |")
    dup_ids = len(topics) - len(topic_ids)
    lines.append(f"| 重复 ID | {dup_ids} |")
    lines.append("")

    # Subject distribution
    lines.append("## 2. 学科分布")
    lines.append("")
    subject_counts = Counter(t["subject"] for t in topics)
    lines.append(f"| 学科 | 数量 | 占比 | 平均先修边 |")
    lines.append(f"|------|------|------|-----------|")
    for subject, count in subject_counts.most_common():
        pct = count / len(topics) * 100
        subject_topics = {t["id"] for t in topics if t["subject"] == subject}
        edges = sum(1 for d in deps if d["topicId"] in subject_topics or d["prerequisiteId"] in subject_topics)
        avg_edges = edges / count if count else 0
        lines.append(f"| {subject} | {count} | {pct:.1f}% | {avg_edges:.1f} |")
    lines.append("")

    # Type distribution
    lines.append("## 3. 知识点类型分布")
    lines.append("")
    type_counts = Counter(t["type"] for t in topics)
    lines.append(f"| 类型 | 数量 | 占比 |")
    lines.append(f"|------|------|------|")
    for typ, count in type_counts.most_common():
        pct = count / len(topics) * 100
        lines.append(f"| {typ} | {count} | {pct:.1f}% |")
    lines.append("")

    # Orphan nodes
    orphans = find_orphan_nodes(topics, deps)
    lines.append("## 4. 孤立节点检测")
    lines.append("")
    lines.append(f"**孤立节点数**: {len(orphans)} (无入边且无出边)")
    lines.append("")
    if orphans:
        lines.append("| Topic ID | 学科 | 名称 |")
        lines.append("|----------|------|------|")
        topic_map = {t["id"]: t for t in topics}
        for oid in orphans[:20]:  # Show first 20
            t = topic_map.get(oid, {})
            lines.append(f"| {oid} | {t.get('subject', '?')} | {t.get('nameZh', t.get('name', '?'))} |")
        if len(orphans) > 20:
            lines.append(f"| ... | ... | 共 {len(orphans)} 个 |")
        lines.append("")
        lines.append("**处理方案**: 标记但不删除，保留图谱完整性。")
    else:
        lines.append("✅ 无孤立节点。")
    lines.append("")

    # Broken links
    broken = find_broken_links(topics, deps)
    lines.append("## 5. 断链检测")
    lines.append("")
    lines.append(f"**断链数**: {len(broken)} (引用不存在的 topic ID)")
    lines.append("")
    if broken:
        lines.append("| 边类型 | 缺失 ID | 来源 |")
        lines.append("|--------|---------|------|")
        for b in broken[:20]:
            dep = b["dep"]
            lines.append(f"| {b['edge']} | {b['value']} | {dep.get('topicId', '?')} → {dep.get('prerequisiteId', '?')} |")
        if len(broken) > 20:
            lines.append(f"| ... | ... | 共 {len(broken)} 条 |")
        lines.append("")
        lines.append("**处理方案**: 在 topic_service 中校验时过滤无效 prerequisite。")
    else:
        lines.append("✅ 无断链。所有依赖引用的 topic ID 均存在。")
    lines.append("")

    # Circular dependencies
    cycles = detect_cycles(topics, deps)
    lines.append("## 6. 循环依赖检测")
    lines.append("")
    lines.append(f"**环路数**: {len(cycles)}")
    lines.append("")
    if cycles:
        lines.append("| # | 环路 (topic IDs) |")
        lines.append("|---|-----------------|")
        topic_map = {t["id"]: t for t in topics}
        for i, cycle in enumerate(cycles[:10], 1):
            names = " → ".join(
                topic_map.get(tid, {}).get("nameZh", topic_map.get(tid, {}).get("name", tid))
                for tid in cycle[:5]
            )
            suffix = " → ..." if len(cycle) > 5 else ""
            lines.append(f"| {i} | {names}{suffix} |")
        if len(cycles) > 10:
            lines.append(f"| ... | 共 {len(cycles)} 个环路 |")
        lines.append("")
        lines.append("**处理方案**: 记录并在 progress_service 中添加防护（避免状态机死锁）。")
    else:
        lines.append("✅ 无循环依赖。图谱为有向无环图 (DAG)。")
    lines.append("")

    # Dependency strength
    strength = analyze_strength_distribution(deps)
    lines.append("## 7. 先修关系强度分布")
    lines.append("")
    lines.append(f"| 强度 | 数量 | 占比 |")
    lines.append(f"|------|------|------|")
    for s, count in sorted(strength.items()):
        pct = count / len(deps) * 100
        lines.append(f"| {s} | {count} | {pct:.1f}% |")
    lines.append("")

    # Age range analysis
    age_stats = analyze_age_ranges(topics)
    lines.append("## 8. 年龄范围覆盖")
    lines.append("")
    lines.append(f"| 学科 | 数量 | 最小年龄 | 最大年龄 | 缺年龄范围 |")
    lines.append(f"|------|------|---------|---------|-----------|")
    for subject, stats in sorted(age_stats.items()):
        lines.append(
            f"| {subject} | {stats['count']} | {stats['min_age']} | {stats['max_age']} | {stats['no_age_range']} |"
        )
    lines.append("")

    # Cluster coverage
    cluster_stats = analyze_clusters(clusters, topics)
    lines.append("## 9. 聚类覆盖率")
    lines.append("")
    lines.append(f"- 聚类总数: {cluster_stats['total_clusters']}")
    lines.append(f"- 领域总数 (subject+domain): {cluster_stats['total_domains']}")
    lines.append(f"- 有聚类的领域: {cluster_stats['domains_with_clusters']}")
    lines.append(f"- 无聚类的领域: {cluster_stats['domains_without_clusters']}")
    lines.append("")
    if cluster_stats["uncovered_domains"]:
        lines.append("**未覆盖领域**:")
        lines.append("")
        lines.append("| 学科 | 领域 | 知识点数 |")
        lines.append("|------|------|---------|")
        for d in cluster_stats["uncovered_domains"]:
            lines.append(f"| {d['subject']} | {d['domain']} | {d['topic_count']} |")
    lines.append("")

    # Translation coverage
    translation = analyze_translation_coverage(topics)
    lines.append("## 10. 中文翻译覆盖率")
    lines.append("")
    lines.append(f"| 字段 | 已翻译 | 翻译率 |")
    lines.append(f"|------|--------|--------|")
    for field, stats in translation.items():
        lines.append(f"| {field} | {stats['count']} | {stats['rate']:.1%} |")
    lines.append("")

    # Cross-subject dependency analysis
    lines.append("## 11. 跨学科依赖分析")
    lines.append("")
    topic_subject = {t["id"]: t["subject"] for t in topics}
    cross_subject = 0
    cross_subject_examples = []
    topic_map = {t["id"]: t for t in topics}
    for d in deps:
        s1 = topic_subject.get(d["topicId"], "?")
        s2 = topic_subject.get(d["prerequisiteId"], "?")
        if s1 != s2 and s1 != "?" and s2 != "?":
            cross_subject += 1
            if len(cross_subject_examples) < 5:
                cross_subject_examples.append(
                    f"{topic_map.get(d['topicId'], {}).get('nameZh', '?')} ({s1}) ← {topic_map.get(d['prerequisiteId'], {}).get('nameZh', '?')} ({s2})"
                )
    lines.append(f"跨学科先修关系: {cross_subject} ({cross_subject / len(deps) * 100:.1f}%)")
    lines.append("")
    if cross_subject_examples:
        lines.append("示例:")
        for ex in cross_subject_examples:
            lines.append(f"- {ex}")
    lines.append("")

    # Summary
    lines.append("## 12. 总结与处理方案")
    lines.append("")
    lines.append("### 数据质量评级")
    lines.append("")

    issues_found = []
    if dup_ids > 0:
        issues_found.append(f"🔴 重复 ID: {dup_ids}")
    if broken:
        issues_found.append(f"🟡 断链: {len(broken)}")
    if cycles:
        issues_found.append(f"🟡 循环依赖: {len(cycles)}")
    if orphans:
        issues_found.append(f"🟢 孤立节点: {len(orphans)} (标记不删除)")

    if not issues_found:
        lines.append("✅ **整体质量良好** — 无严重问题。")
    else:
        for issue in issues_found:
            lines.append(f"- {issue}")

    lines.append("")
    lines.append("### 处理方案汇总")
    lines.append("")
    lines.append("| 问题类型 | 处理方案 | 影响范围 |")
    lines.append("|---------|---------|---------|")
    lines.append("| 孤立节点 | 标记但不删除，保留完整性 | 仅影响图谱可视化 |")
    lines.append("| 循环依赖 | 记录并在 progress_service 中添加防护 | 状态机需检测环路避免死锁 |")
    lines.append("| 断链 | 在 topic_service 校验时过滤无效 prerequisite | 先修关系查询需做 null 检查 |")
    lines.append("| 未覆盖领域 | Phase 7 扩展时优先补充 | 不影响当前 MVP |")
    lines.append("")

    return "\n".join(lines)


def main():
    base_dir = Path(__file__).parent.parent / "packages" / "os_taxonomy"
    if not base_dir.exists():
        # Try alternate path
        base_dir = Path("server/packages/os_taxonomy")
    if not base_dir.exists():
        print("ERROR: Cannot find os_taxonomy data directory", file=sys.stderr)
        sys.exit(1)

    report = generate_report(base_dir)

    # Write to reports directory
    output_path = Path("docs/superpowers/reports/phase0-data-quality-report.md")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")
    print(f"Report written to: {output_path}")
    print(f"Report length: {len(report)} chars, {len(report.splitlines())} lines")


if __name__ == "__main__":
    main()
