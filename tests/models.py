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
    owner = models.ForeignKey(TestPerson, blank=True, null=True)
