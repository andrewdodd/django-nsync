from django.core.exceptions import ObjectDoesNotExist
#from nsync.models import ExternalSystem, ExternalReferenceHandler

class ModelAction:
    def __init__(self, model, match_field_name, fields={}):
        if model is None:
            raise ValueError('model cannot be None')
        if not match_field_name:
            raise ValueError('match_field_name({}) must be not "empty"'.format(match_field_name))
        if match_field_name not in fields:
            raise ValueError('match_field_name({}) must be in fields'.format(match_field_name))

        self.model = model
        self.match_field_name = match_field_name
        self.fields = fields

    def __str__(self):
        return "Action {} - Model:{} - MatchField:{} - Fields:{}".format(
                self.__class__,
                self.model,
                self.match_field_name,
                self.fields)

    def find_objects(self):
        filter_by = {self.match_field_name: self.fields[self.match_field_name]}
        return self.model.objects.filter(**filter_by)

    def execute(self):
        pass
        

class CreateModelAction(ModelAction):
    def execute(self):
        if self.find_objects().exists():
            # already exists, return None
            return None

        obj = self.model(**self.fields)
        obj.save()
        return obj


class UpdateModelAction(ModelAction):
    def execute(self):
        try:
            obj = self.find_objects().get()

            for field, value in self.fields.items():
                setattr(obj, field, value)
            obj.save()

            return obj
        except ObjectDoesNotExist:
            return None

class DeleteModelAction(ModelAction):
    def execute(self):
        self.find_objects().delete()

class ActionsBuilder:
    action_flags_label = 'action_flags'
    match_field_name_label = 'match_field_name'
    external_key_label = 'external_key'

    def __init__(self, model):
        self.model = model

    def from_dict(self, raw_values):
        if not raw_values:
            return []

        action_flags = raw_values.pop(self.action_flags_label)
        match_field_name = raw_values.pop(self.match_field_name_label)
        external_system_key = raw_values.pop(self.external_key_label, None)

        encoded_actions = EncodedSyncActions.decode(action_flags)

        return self.build(encoded_actions, match_field_name, external_system_key, raw_values)

    def build(self, encoded_actions, match_field_name, external_system_key, raw_values):

        actions = []


        if encoded_actions.create:
            actions.append(CreateModelAction(self.model, match_field_name, raw_values))
        if encoded_actions.update:
            actions.append(UpdateModelAction(self.model, match_field_name, raw_values))
        if encoded_actions.delete:
            actions.append(DeleteModelAction(self.model, match_field_name, raw_values))

        if not actions:
            actions.append(ModelAction(self.model, match_field_name, raw_values))


        return actions


class EncodedSyncActions:
    def __init__(self, create=False, update=False, delete=False, force=False):
        if delete and create:
            raise ValueError("Cannot delete AND create")
        if delete and update:
            raise ValueError("Cannot delete AND update")

        self.create = create
        self.update = update
        self.delete = delete
        self.force = force

    def encode(self):
        return "{}{}{}{}".format(
                'c' if self.create else '', 
                'u' if self.update else '',
                'd' if self.delete else '',
                '*' if self.force else '')

    def __str__(self):
        return "SyncActions {}".format(self.encode())

        def is_impotent(self):
            return not (self.create or self.update or self.delete)

    @staticmethod
    def decode(action_flags):
        create = False
        update = False
        delete = False
        force = False

        if action_flags:
            try:
                create = 'C' in action_flags or 'c' in action_flags
                update = 'U' in action_flags or 'u' in action_flags
                delete = 'D' in action_flags or 'd' in action_flags
                force = '*' in action_flags
            except TypeError:
                pass # not iterable

        return EncodedSyncActions(create, update, delete, force)



