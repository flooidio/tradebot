"""
GenAI integration for narrative explanations and post-trade analysis.
"""
from typing import Dict, List, Optional
import os
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class GenAIAnalyst:
    """
    GenAI integration for trading analysis.
    Uses AI for narrative explanations, not direct trading decisions.
    """
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4"):
        """
        Initialize GenAI analyst.
        
        Args:
            api_key: OpenAI API key (optional, can be set via env var)
            model: Model to use (default: gpt-4)
        """
        self.api_key = api_key
        self.model = model
        self.client = None
        
        # Initialize client if API key provided
        if api_key:
            try:
                import openai
                self.client = openai.OpenAI(api_key=api_key)
            except ImportError:
                logger.warning("OpenAI library not installed. GenAI features disabled.")
    
    def explain_entry(self, strategy_mode: str, signals: Dict, reason: str) -> str:
        """
        Generate narrative explanation for trade entry.
        
        Args:
            strategy_mode: Selected strategy
            signals: Market signals that triggered entry
            reason: Technical reason for entry
        
        Returns:
            Narrative explanation
        """
        if not self.client:
            return f"Entered {strategy_mode} based on {reason}"
        
        prompt = f"""
        Explain why a trading bot entered a {strategy_mode} position.
        
        Signals:
        {self._format_signals(signals)}
        
        Reason: {reason}
        
        Provide a clear, concise explanation suitable for a trading journal.
        """
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a trading analyst explaining trade entries."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=200
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Error generating entry explanation: {e}")
            return f"Entered {strategy_mode} based on {reason}"
    
    def explain_exit(self, group_name: str, exit_reason: str, pnl: float) -> str:
        """
        Generate narrative explanation for trade exit.
        
        Args:
            group_name: Name of position
            exit_reason: Reason for exit
            pnl: Profit/loss
        
        Returns:
            Narrative explanation
        """
        if not self.client:
            return f"Exited {group_name}: {exit_reason}, P/L: ${pnl:.2f}"
        
        prompt = f"""
        Explain why a trading bot exited a position.
        
        Position: {group_name}
        Exit Reason: {exit_reason}
        P/L: ${pnl:.2f}
        
        Provide a clear explanation of the exit decision and outcome.
        """
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a trading analyst explaining trade exits."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=200
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Error generating exit explanation: {e}")
            return f"Exited {group_name}: {exit_reason}, P/L: ${pnl:.2f}"
    
    def review_trade(self, group, market_data: Dict) -> Dict:
        """
        Post-trade review with pattern extraction.
        
        Args:
            group: Closed group
            market_data: Market data during trade
        
        Returns:
            Review dictionary with insights
        """
        review = {
            "group_name": group.name,
            "entry_time": group.opendt.isoformat() if group.opendt else None,
            "exit_time": group.closedt.isoformat() if group.closedt else None,
            "pnl": group.profit * 100 * group.qty,
            "duration": None,
            "insights": []
        }
        
        if group.opendt and group.closedt:
            duration = group.closedt - group.opendt
            review["duration"] = str(duration)
        
        # Extract patterns
        if group.profit > 0:
            review["insights"].append("Profitable trade")
        else:
            review["insights"].append("Loss - review entry conditions")
        
        # GenAI analysis if available
        if self.client:
            prompt = f"""
            Review this options trade:
            Strategy: {group.name}
            P/L: ${review['pnl']:.2f}
            Duration: {review['duration']}
            
            Provide 2-3 insights about what went well or could be improved.
            """
            
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You are a trading analyst reviewing trades."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=300
                )
                review["ai_insights"] = response.choices[0].message.content
            except Exception as e:
                logger.error(f"Error generating trade review: {e}")
        
        return review
    
    def detect_contradictions(self, rules: List[str], actions: List[Dict]) -> List[str]:
        """
        Detect contradictions between trading rules and actions.
        
        Args:
            rules: List of trading rules
            actions: List of actions taken
        
        Returns:
            List of detected contradictions
        """
        contradictions = []
        
        # Simple rule checking (can be enhanced with GenAI)
        for action in actions:
            # Check if action violates any rules
            # (simplified - would need full rule engine)
            pass
        
        # GenAI analysis if available
        if self.client and len(contradictions) == 0:
            prompt = f"""
            Check if these trading actions contradict the stated rules:
            
            Rules:
            {chr(10).join(rules)}
            
            Actions:
            {self._format_actions(actions)}
            
            List any contradictions found.
            """
            
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You are a trading rule compliance checker."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=200
                )
                ai_contradictions = response.choices[0].message.content
                if "no contradiction" not in ai_contradictions.lower():
                    contradictions.append(ai_contradictions)
            except Exception as e:
                logger.error(f"Error checking contradictions: {e}")
        
        return contradictions
    
    def generate_improvements(self, journal_data: Dict) -> List[str]:
        """
        Generate weekly improvement suggestions from trading logs.
        
        Args:
            journal_data: Journal data for the week
        
        Returns:
            List of improvement suggestions
        """
        suggestions = []
        
        if not self.client:
            return suggestions
        
        prompt = f"""
        Analyze this trading week and suggest improvements:
        
        {json.dumps(journal_data, indent=2)}
        
        Provide 3-5 specific, actionable improvements.
        """
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a trading coach providing improvement suggestions."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=400
            )
            suggestions_text = response.choices[0].message.content
            # Parse suggestions (simplified)
            suggestions = [s.strip() for s in suggestions_text.split("\n") if s.strip() and s.strip()[0].isdigit()]
        except Exception as e:
            logger.error(f"Error generating improvements: {e}")
        
        return suggestions
    
    def _format_signals(self, signals: Dict) -> str:
        """Format signals dict for prompt."""
        return "\n".join([f"{k}: {v}" for k, v in signals.items()])
    
    def _format_actions(self, actions: List[Dict]) -> str:
        """Format actions list for prompt."""
        return "\n".join([json.dumps(a, indent=2) for a in actions])


# Helper function for optional GenAI usage
def get_genai_analyst(api_key: Optional[str] = None) -> Optional[GenAIAnalyst]:
    """Get GenAI analyst instance if API key available."""
    if api_key or os.environ.get("OPENAI_API_KEY"):
        return GenAIAnalyst(api_key=api_key or os.environ.get("OPENAI_API_KEY"))
    return None
