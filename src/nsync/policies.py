from django.db import transaction


class BasicSyncPolicy:
    """A synchronisation policy that simply executes each action in order."""
    def __init__(self, actions):
        """
        Create a basic synchronisation policy.

        :param actions: The list of actions to perform
        :return: Nothing
        """
        self.actions = actions

    def execute(self):
        for action in self.actions:
            action.execute()


class TransactionSyncPolicy:
    """
    A synchronisation policy that wraps other sync policies in a database
    transaction.

    This allows the changes from all of the actions to occur in an atomic
    fashion. The limit to the number of transactions is database dependent
    but is usually quite large (i.e. like 2^32).
    """
    def __init__(self, policy):
        self.policy = policy

    def execute(self):
        with transaction.atomic():
            self.policy.execute()


class OrderedSyncPolicy:
    """
    A synchronisation policy that performs the actions in a controlled order.

    This policy filters the list of actions and executes all of the create
    actions, then all of the update actions and finally all of the delete
    actions. This is to ensure that the whole list of actions behaves more
    predictably.

    For example, if there are create actions and forced delete actions for
    the same object in the list, then the net result of the state of the
    objects will depend on which action is performed first. If the order is
    'create' then 'delete', the object will be created and then deleted. If
    the order is 'delete' then 'create', the delete action will fail and
    then the object will be created. This policy avoids this situation by
    performing the different types in order.

    This also helps with referential updates, where an update action might be
    earlier in the list than the action to create the referred to object.
    """
    def __init__(self, actions):
        self.actions = actions

    def execute(self):
        for filter_by in ['create', 'update', 'delete']:
            filtered_actions = filter(lambda a: a.type == filter_by,
                                      self.actions)
            for action in filtered_actions:
                action.execute()
