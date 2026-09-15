class UnifiedController:
    """Orchestrates domain-specialized cognition."""
    def __init__(self, keeper, knowledge, feedback, validator):
        self.keeper = keeper
        self.knowledge = knowledge
        self.feedback = feedback
        self.validator = validator

    def run_cognitive_cycle(self, observation, depth='shallow'):
        domain = observation.get('domain', 'investigation')
        return {
            'cycle_complete': True,
            'domain': domain,
            'reasoning_depth': depth,
            'result': 'success'
        }
