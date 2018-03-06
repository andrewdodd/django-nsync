from django.db import models


class TestPerson(models.Model):
    first_name = models.CharField(
        blank=False,
        max_length=50,
        verbose_name='First Name'
    )
    last_name = models.CharField(
        blank=False,
        max_length=50,
        verbose_name='Last Name'
    )
    age = models.IntegerField(blank=True, null=True)
    hair_colour = models.CharField(
        blank=False,
        max_length=50,
        default="Unknown")

    def __str__(self):
        return '{}:{} {} - {}'.format(self.id,
                                      self.first_name,
                                      self.last_name,
                                      self.age)


class TestHouse(models.Model):
    address = models.CharField(max_length=100)
    country = models.CharField(max_length=100, blank=True)
    floors = models.IntegerField(blank=True, null=True)
    owner = models.ForeignKey(TestPerson, blank=True, null=True, related_name='houses',
        on_delete=models.CASCADE)
    built = models.DateField(blank=True, null=True)

    def __str__(self):
        return '{} - {}{}{}{}'.format(
            self.address,
            self.built,
            ', {}'.format(self.country) if self.country else '',
            ' - {} floors'.format(self.floors) if self.floors else '',
            ' - Family:{}'.format(self.owner.last_name) if self.owner else '')


class TestBuilder(TestPerson):
    company = models.CharField(
        blank=False,
        max_length=50,
        default='Self employed'
    )
    buildings = models.ManyToManyField(
        TestHouse,
        related_name='builders'
    )


