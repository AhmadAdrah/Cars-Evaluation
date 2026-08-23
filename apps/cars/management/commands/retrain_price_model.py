from django.core.management.base import BaseCommand, CommandError

from apps.cars.services.model_training_service import DEFAULT_DATA_PATH, train_and_save_model


class Command(BaseCommand):
    help = 'Retrain the used-car price prediction model from the cleaned dataset.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--data',
            type=str,
            default=None,
            help=f'Path to training CSV (default: {DEFAULT_DATA_PATH})',
        )

    def handle(self, *args, **options):
        data_path = options.get('data')
        self.stdout.write(self.style.MIGRATE_HEADING('Retraining price model...'))
        try:
            metrics = train_and_save_model(data_path=data_path)
        except Exception as exc:
            raise CommandError(f'Training failed: {exc}')

        self.stdout.write(self.style.SUCCESS(
            f"MAE: {metrics['mae']} | R2: {metrics['r2']} | rows: {metrics['rows']}"
        ))
        self.stdout.write(self.style.SUCCESS(
            f"target transform: {metrics['target_transform']} | encoded features: {metrics['encoded_features']}"
        ))
        self.stdout.write(self.style.SUCCESS(f"Model saved to: {metrics['model_path']}"))
