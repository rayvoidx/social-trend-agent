"""
YouTube 영상 고급 분석 모듈

자막 다운로드, 세그먼트 분석, 고급 메타데이터 추출 기능 제공
"""

from __future__ import annotations

import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class YouTubeAnalyzer:
    """YouTube 영상 고급 분석 클래스"""

    def __init__(self, yt_dlp_path: Optional[str] = None):
        """
        Args:
            yt_dlp_path: yt-dlp 실행 파일 경로 (None이면 시스템 PATH에서 찾음)
        """
        self.yt_dlp_path = yt_dlp_path or "yt-dlp"
        self.temp_dir = Path(tempfile.gettempdir()) / "youtube_analysis"
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def _check_yt_dlp(self) -> bool:
        """yt-dlp가 설치되어 있는지 확인"""
        try:
            result = subprocess.run(
                [self.yt_dlp_path, "--version"], capture_output=True, text=True, timeout=5
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def download_subtitles(
        self,
        video_url: str,
        languages: List[str] = ["ko", "en"],
        output_dir: Optional[Path] = None,
        return_content: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """YouTube 영상에서 자막 다운로드

        Args:
            video_url: YouTube 영상 URL
            languages: 다운로드할 자막 언어 목록 (기본: 한국어, 영어)
            output_dir: 저장할 디렉토리 (None이면 임시 디렉토리)
            return_content: True면 파일 경로와 함께 내용도 반환

        Returns:
            Dict[language, file_path] 또는 Dict[language, {"path": str, "content": str}] (return_content=True)
            또는 None (실패 시)
        """
        if not self._check_yt_dlp():
            logger.warning("yt-dlp가 설치되지 않았습니다. pip install yt-dlp")
            return None

        output_dir = output_dir or self.temp_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        subtitle_files: Dict[str, str] = {}

        for lang in languages:
            try:
                # 자막 다운로드 (SRT 형식)
                output_template = str(output_dir / f"%(id)s.%(ext)s")
                cmd = [
                    self.yt_dlp_path,
                    "--write-sub",
                    "--write-auto-sub",  # 자동 생성 자막도 포함
                    "--sub-lang",
                    lang,
                    "--sub-format",
                    "srt",
                    "--skip-download",
                    "--no-warnings",
                    "-o",
                    output_template,
                    video_url,
                ]

                result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

                if result.returncode == 0:
                    # 다운로드된 파일 찾기
                    video_id = self._extract_video_id(video_url)
                    if video_id:
                        # 여러 가능한 파일명 패턴 시도
                        possible_files = [
                            output_dir / f"{video_id}.{lang}.srt",
                            output_dir / f"{video_id}.{lang}.vtt",
                            output_dir / f"{video_id}.{lang}.srt",
                        ]

                        # 와일드카드로 찾기
                        import glob

                        pattern = str(output_dir / f"*{video_id}*.{lang}.*")
                        found_files = glob.glob(pattern)

                        srt_file = None
                        for possible in possible_files + [Path(f) for f in found_files]:
                            if possible.exists() and possible.suffix in (".srt", ".vtt"):
                                srt_file = possible
                                break

                        if srt_file and srt_file.exists():
                            if return_content:
                                try:
                                    with open(srt_file, "r", encoding="utf-8") as f:
                                        content = f.read()
                                    subtitle_files[lang] = {
                                        "path": str(srt_file),
                                        "content": content,
                                    }
                                except Exception as e:
                                    logger.warning(f"자막 파일 읽기 실패 ({lang}): {e}")
                                    subtitle_files[lang] = {"path": str(srt_file), "content": ""}
                            else:
                                subtitle_files[lang] = str(srt_file)
                            logger.info(f"자막 다운로드 완료: {lang} -> {srt_file}")

            except subprocess.TimeoutExpired:
                logger.warning(f"자막 다운로드 타임아웃: {lang}")
            except Exception as e:
                logger.warning(f"자막 다운로드 실패 ({lang}): {e}")

        return subtitle_files if subtitle_files else None

    @staticmethod
    def extract_video_id(url: str) -> Optional[str]:
        """YouTube URL에서 비디오 ID 추출 (정적 메서드)"""
        import re

        patterns = [
            r"(?:youtube\.com\/watch\?v=|youtu\.be\/)([a-zA-Z0-9_-]{11})",
            r"youtube\.com\/embed\/([a-zA-Z0-9_-]{11})",
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    def _extract_video_id(self, url: str) -> Optional[str]:
        """인스턴스 메서드 래퍼"""
        return self.extract_video_id(url)

    def analyze_subtitle_segments(
        self, subtitle_path: str, segment_duration: int = 60
    ) -> List[Dict[str, Any]]:
        """자막 파일을 분석하여 세그먼트별 정보 추출

        Args:
            subtitle_path: SRT 자막 파일 경로
            segment_duration: 세그먼트 길이 (초, 기본: 60초)

        Returns:
            세그먼트별 정보 리스트
        """
        segments: List[Dict[str, Any]] = []

        try:
            with open(subtitle_path, "r", encoding="utf-8") as f:
                content = f.read()

            # SRT 파싱
            blocks = content.split("\n\n")
            current_segment_start = 0
            current_segment_text: List[str] = []

            for block in blocks:
                lines = [l.strip() for l in block.split("\n") if l.strip()]
                if len(lines) < 2:
                    continue

                # 타임코드 파싱
                timecode_line = None
                for line in lines:
                    if "-->" in line:
                        timecode_line = line
                        break

                if not timecode_line:
                    continue

                start_str, end_str = timecode_line.split("-->")
                start_seconds = self._parse_timecode(start_str.strip())
                end_seconds = self._parse_timecode(end_str.strip())

                # 텍스트 추출
                text_lines = [l for l in lines if "-->" not in l and not l.isdigit()]
                text = " ".join(text_lines)

                # 세그먼트 분할
                if start_seconds >= current_segment_start + segment_duration:
                    if current_segment_text:
                        segments.append(
                            {
                                "start_seconds": current_segment_start,
                                "end_seconds": start_seconds,
                                "duration": start_seconds - current_segment_start,
                                "text": " ".join(current_segment_text),
                                "word_count": len(" ".join(current_segment_text).split()),
                            }
                        )
                    current_segment_start = start_seconds
                    current_segment_text = []

                current_segment_text.append(text)

            # 마지막 세그먼트
            if current_segment_text:
                segments.append(
                    {
                        "start_seconds": current_segment_start,
                        "end_seconds": (
                            end_seconds
                            if "end_seconds" in locals()
                            else current_segment_start + segment_duration
                        ),
                        "duration": (
                            end_seconds
                            if "end_seconds" in locals()
                            else current_segment_start + segment_duration
                        )
                        - current_segment_start,
                        "text": " ".join(current_segment_text),
                        "word_count": len(" ".join(current_segment_text).split()),
                    }
                )

        except Exception as e:
            logger.error(f"자막 분석 실패: {e}")

        return segments

    def _parse_timecode(self, timecode: str) -> int:
        """SRT 타임코드를 초 단위로 변환"""
        try:
            # 형식: HH:MM:SS,mmm 또는 HH:MM:SS.mmm
            timecode = timecode.replace(",", ":").replace(".", ":")
            parts_str = timecode.split(":")
            parts: List[int] = []
            for p in parts_str:
                if p.isdigit():
                    parts.append(int(p))

            while len(parts) < 3:
                parts.insert(0, 0)

            hours, minutes, seconds = parts[:3]
            return hours * 3600 + minutes * 60 + seconds
        except Exception:
            return 0

    def extract_keywords_from_segments(
        self, segments: List[Dict[str, Any]], top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """세그먼트에서 키워드 추출

        Args:
            segments: 세그먼트 리스트
            top_k: 상위 K개 키워드

        Returns:
            키워드 및 빈도 정보
        """
        from collections import Counter
        import re

        all_words = []
        for segment in segments:
            text = segment.get("text", "")
            # 한글, 영문 단어 추출
            words = re.findall(r"[가-힣]+|[a-zA-Z]{3,}", text.lower())
            all_words.extend(words)

        # 불용어 제거
        stop_words = {
            "the",
            "a",
            "an",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
            "이",
            "그",
            "저",
            "의",
            "을",
            "를",
            "에",
            "에서",
            "로",
            "으로",
            "와",
            "과",
            "는",
            "은",
            "가",
        }

        filtered_words = [w for w in all_words if w not in stop_words and len(w) > 1]
        word_freq = Counter(filtered_words)

        keywords = []
        for word, freq in word_freq.most_common(top_k):
            segment_indices: List[int] = []
            for i, s in enumerate(segments):
                if word in s.get("text", "").lower():
                    segment_indices.append(i)

            keywords.append({"word": word, "frequency": freq, "segments": segment_indices})

        return keywords

    def generate_segment_summaries(
        self, segments: List[Dict[str, Any]], max_summary_length: int = 100
    ) -> List[Dict[str, Any]]:
        """세그먼트별 요약 생성 (간단한 규칙 기반)

        Args:
            segments: 세그먼트 리스트
            max_summary_length: 최대 요약 길이

        Returns:
            요약이 포함된 세그먼트 리스트
        """
        for segment in segments:
            text = segment.get("text", "")
            if not text:
                segment["summary"] = ""
                continue

            # 간단한 요약: 첫 문장 + 키워드
            sentences = text.split(".")
            first_sentence = sentences[0].strip() if sentences else ""

            # 키워드 추출 (상위 3개)
            words = text.split()
            important_words = [w for w in words if len(w) > 3][:3]

            summary = first_sentence
            if important_words and len(summary) < max_summary_length:
                summary += f" ({', '.join(important_words)})"

            segment["summary"] = summary[:max_summary_length]

        return segments
