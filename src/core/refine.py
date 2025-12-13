"""
Self-Refinement Utilities
"""

import logging
from typing import Optional, Dict, Any, Type, TypeVar
from pydantic import BaseModel

from src.integrations.llm.llm_client import LLMClient
from src.domain.schemas import TrendInsight, QualityCheck, RefinementResult

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class RefineEngine:
    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client

    def generate(
        self,
        prompt: str,
        schema: Type[T],
        system_prompt: str = "You are a helpful assistant.",
        **kwargs,
    ) -> Optional[T]:
        """구조화된 출력 생성"""
        try:
            result_dict = self.llm.chat_json(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                schema=schema.model_json_schema(),
                temperature=0.7,
                **kwargs,
            )
            return schema.model_validate(result_dict)
        except Exception as e:
            logger.error(f"Generation failed: {e}")
            return None

    def evaluate(self, content: BaseModel, criteria: str, **kwargs) -> QualityCheck:
        """콘텐츠 품질 평가"""
        prompt = f"""
        Evaluate the following content based on these criteria:
        {criteria}

        Content:
        {content.model_dump_json(indent=2)}
        """

        result = self.generate(
            prompt,
            QualityCheck,
            system_prompt="You are a strict quality assurance auditor.",
            **kwargs,
        )

        if not result:
            # Fallback if evaluation fails
            return QualityCheck(score=5, feedback="Evaluation failed", is_pass=False)

        return result

    def refine_loop(
        self, prompt: str, initial_schema: Type[T], criteria: str, max_iterations: int = 2, **kwargs
    ) -> T:
        """
        생성 -> 평가 -> 개선 루프 실행
        """
        # 1. Draft
        current_content = self.generate(
            prompt,
            initial_schema,
            system_prompt="You are an expert analyst. Provide high-quality structured output.",
            **kwargs,
        )

        if not current_content:
            raise ValueError("Failed to generate initial draft")

        for i in range(max_iterations):
            # 2. Evaluate
            quality = self.evaluate(current_content, criteria, **kwargs)
            logger.info(
                f"Iteration {i+1} Quality Score: {quality.score}/10 - Pass: {quality.is_pass}"
            )

            if quality.is_pass:
                return current_content

            # 3. Refine
            refine_prompt = f"""
            The previous output needs improvement based on this feedback:
            {quality.feedback}
            
            Specific issues:
            {", ".join(quality.issues)}
            
            Please rewrite the content to address these issues while maintaining the original structure.
            
            Original Request:
            {prompt}
            """

            refined = self.generate(
                refine_prompt,
                initial_schema,
                system_prompt="You are an expert editor. Improve the content based on feedback.",
                **kwargs,
            )

            if refined:
                current_content = refined
            else:
                logger.warning("Refinement generation failed, keeping previous version")
                break

        return current_content
