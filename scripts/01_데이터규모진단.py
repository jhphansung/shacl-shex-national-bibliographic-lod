# -*- coding: utf-8 -*-
"""
국가서지 LOD 데이터 규모 진단 스크립트
연구: SHACL과 ShEx를 활용한 국가서지 LOD 품질 평가
"""

import os
import json
import glob
import csv
from collections import defaultdict, Counter
from datetime import datetime

# ============================================================
# 설정: 데이터 루트 경로 (사용자 환경에 맞게 수정)
# ============================================================
DATA_ROOT = r"D:\데이터"

FOLDERS = {
    "기타-도서관정보": "기타도서관정보Library_json_20260401",
    "서지-오프라인자료": "서지데이터오프라인자료Offline_json_20260401",
    "서지-온라인자료": "서지데이터온라인자료Online_json_20260401",
    "전거-개인명": "전거데이터개인명Person_json_20260401",
    "전거-단체명": "전거데이터단체명Organization_json_20260401",
    "전거-주제명": "전거데이터주제명Concept_json_20260401",
}

OUTPUT_DIR = os.path.join(DATA_ROOT, "_분석결과")


def detect_jsonld_records(obj):
    """JSON-LD 구조에서 레코드(노드) 리스트를 추출한다."""
    if isinstance(obj, dict):
        if "@graph" in obj:
            return obj["@graph"]
        else:
            return [obj]
    elif isinstance(obj, list):
        return obj
    return []


def get_types(record):
    """레코드의 @type 값을 리스트로 정규화하여 반환한다."""
    t = record.get("@type", record.get("rdf:type", None))
    if t is None:
        return []
    if isinstance(t, str):
        return [t]
    if isinstance(t, list):
        result = []
        for item in t:
            if isinstance(item, str):
                result.append(item)
            elif isinstance(item, dict):
                result.append(item.get("@id", str(item)))
        return result
    if isinstance(t, dict):
        return [t.get("@id", str(t))]
    return []


def count_triples(record):
    """한 레코드(노드)가 표현하는 대략적인 트리플 수를 센다."""
    count = 0
    for key, value in record.items():
        if key in ("@context",):
            continue
        if key == "@id":
            continue
        if isinstance(value, list):
            count += len(value)
        else:
            count += 1
    return count


def analyze_folder(folder_label, folder_path):
    """단일 폴더를 스캔하여 통계를 산출한다."""
    stats = {
        "folder_label": folder_label,
        "folder_path": folder_path,
        "file_count": 0,
        "total_size_bytes": 0,
        "record_count": 0,
        "triple_count": 0,
        "class_counter": Counter(),
        "property_counter": Counter(),
        "namespace_counter": Counter(),
        "parse_errors": [],
    }

    if not os.path.isdir(folder_path):
        stats["parse_errors"].append(f"폴더 없음: {folder_path}")
        return stats

    json_files = glob.glob(os.path.join(folder_path, "**", "*.json"), recursive=True)
    json_files += glob.glob(os.path.join(folder_path, "**", "*.jsonld"), recursive=True)
    json_files = sorted(set(json_files))

    stats["file_count"] = len(json_files)

    for fpath in json_files:
        try:
            stats["total_size_bytes"] += os.path.getsize(fpath)
        except OSError:
            pass

        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            stats["parse_errors"].append(f"JSON 파싱 오류: {os.path.basename(fpath)} ({e})")
            continue
        except UnicodeDecodeError:
            try:
                with open(fpath, "r", encoding="utf-8-sig") as f:
                    data = json.load(f)
            except Exception as e:
                stats["parse_errors"].append(f"인코딩 오류: {os.path.basename(fpath)} ({e})")
                continue
        except Exception as e:
            stats["parse_errors"].append(f"읽기 오류: {os.path.basename(fpath)} ({e})")
            continue

        records = detect_jsonld_records(data)

        for record in records:
            if not isinstance(record, dict):
                continue
            stats["record_count"] += 1
            stats["triple_count"] += count_triples(record)

            for tp in get_types(record):
                stats["class_counter"][tp] += 1

            for key in record.keys():
                if key in ("@context", "@id", "@type"):
                    continue
                stats["property_counter"][key] += 1
                if ":" in key:
                    prefix = key.split(":")[0]
                    stats["namespace_counter"][prefix] += 1
                elif key.startswith("http"):
                    stats["namespace_counter"]["(full-uri)"] += 1

    return stats


def format_size(num_bytes):
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if num_bytes < 1024.0:
            return f"{num_bytes:.2f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.2f} PB"


def main():
    print("=" * 70)
    print("국가서지 LOD 데이터 규모 진단")
    print(f"분석 일시: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"데이터 루트: {DATA_ROOT}")
    print("=" * 70)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    all_stats = []
    grand_total = {
        "file_count": 0,
        "record_count": 0,
        "triple_count": 0,
        "size_bytes": 0,
    }

    global_class_counter = Counter()
    global_property_counter = Counter()
    global_namespace_counter = Counter()

    for label, folder_name in FOLDERS.items():
        folder_path = os.path.join(DATA_ROOT, folder_name)
        print(f"\n[분석 중] {label}")
        print(f"  경로: {folder_path}")

        s = analyze_folder(label, folder_path)
        all_stats.append(s)

        grand_total["file_count"] += s["file_count"]
        grand_total["record_count"] += s["record_count"]
        grand_total["triple_count"] += s["triple_count"]
        grand_total["size_bytes"] += s["total_size_bytes"]

        global_class_counter.update(s["class_counter"])
        global_property_counter.update(s["property_counter"])
        global_namespace_counter.update(s["namespace_counter"])

        print(f"  파일 수: {s['file_count']:,}")
        print(f"  용량: {format_size(s['total_size_bytes'])}")
        print(f"  레코드(노드) 수: {s['record_count']:,}")
        print(f"  추정 트리플 수: {s['triple_count']:,}")
        print(f"  클래스 종류: {len(s['class_counter'])}")
        if s["class_counter"]:
            print("  주요 클래스 (상위 5):")
            for cls, cnt in s["class_counter"].most_common(5):
                print(f"    - {cls}: {cnt:,}")
        if s["parse_errors"]:
            print(f"  [경고] 오류 {len(s['parse_errors'])}건 발생")
            for err in s["parse_errors"][:3]:
                print(f"    {err}")

    # ============================================================
    # 전체 종합
    # ============================================================
    print("\n" + "=" * 70)
    print("전체 종합")
    print("=" * 70)
    print(f"총 파일 수: {grand_total['file_count']:,}")
    print(f"총 용량: {format_size(grand_total['size_bytes'])}")
    print(f"총 레코드(노드) 수: {grand_total['record_count']:,}")
    print(f"총 추정 트리플 수: {grand_total['triple_count']:,}")
    print(f"전체 클래스 종류: {len(global_class_counter)}")
    print(f"전체 속성 종류: {len(global_property_counter)}")

    print("\n[전체 클래스별 인스턴스 수]")
    for cls, cnt in global_class_counter.most_common():
        print(f"  {cls}: {cnt:,}")

    print("\n[네임스페이스별 속성 출현 빈도]")
    for ns, cnt in global_namespace_counter.most_common():
        print(f"  {ns}: {cnt:,}")

    print("\n[전체 속성별 출현 빈도 (상위 30)]")
    for prop, cnt in global_property_counter.most_common(30):
        print(f"  {prop}: {cnt:,}")

    # ============================================================
    # 결과를 CSV로 저장
    # ============================================================
    # 1. 폴더별 요약
    summary_csv = os.path.join(OUTPUT_DIR, "01_폴더별_요약.csv")
    with open(summary_csv, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["폴더", "파일수", "용량(MB)", "레코드수", "추정트리플수", "클래스종류수"])
        for s in all_stats:
            w.writerow([
                s["folder_label"],
                s["file_count"],
                f"{s['total_size_bytes']/1024/1024:.2f}",
                s["record_count"],
                s["triple_count"],
                len(s["class_counter"]),
            ])

    # 2. 클래스별 인스턴스 수
    class_csv = os.path.join(OUTPUT_DIR, "02_클래스별_인스턴스수.csv")
    with open(class_csv, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["클래스", "인스턴스수"])
        for cls, cnt in global_class_counter.most_common():
            w.writerow([cls, cnt])

    # 3. 속성별 출현 빈도
    prop_csv = os.path.join(OUTPUT_DIR, "03_속성별_출현빈도.csv")
    with open(prop_csv, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["속성", "출현빈도"])
        for prop, cnt in global_property_counter.most_common():
            w.writerow([prop, cnt])

    # 4. 폴더별 상세 (클래스 분포)
    detail_csv = os.path.join(OUTPUT_DIR, "04_폴더별_클래스분포.csv")
    with open(detail_csv, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["폴더", "클래스", "인스턴스수"])
        for s in all_stats:
            for cls, cnt in s["class_counter"].most_common():
                w.writerow([s["folder_label"], cls, cnt])

    print("\n" + "=" * 70)
    print("결과 파일 저장 완료")
    print(f"  저장 위치: {OUTPUT_DIR}")
    print("  - 01_폴더별_요약.csv")
    print("  - 02_클래스별_인스턴스수.csv")
    print("  - 03_속성별_출현빈도.csv")
    print("  - 04_폴더별_클래스분포.csv")
    print("=" * 70)


if __name__ == "__main__":
    main()
