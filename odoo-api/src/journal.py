try:
    from .api import OdooAPI
except ImportError:
    import sys
    import os
    # Add the parent directory to sys.path to allow absolute imports
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from odoo_lib.api import OdooAPI
import pandas as pd
from datetime import datetime


class OdooJournal(OdooAPI):
    def __init__(self, database='test'):
        super().__init__(database=database)

#CRUD

    def create_journal_entries(self, journal_name, entries_df):
        """
        Crea líneas de extracto bancario y las concilia automáticamente con los asientos contables correspondientes
        """
        try:
            print(f"\nBuscando diario '{journal_name}'...")
            journal = self.models.execute_kw(
                self.db, self.uid, self.password,
                'account.journal', 'search_read',
                [[['name', '=', journal_name]]],
                {'fields': ['id', 'default_account_id']}
            )

            if not journal:
                return f"No se encontró el diario {journal_name}"

            journal_id = journal[0]['id']
            print(f"ID del diario encontrado: {journal_id}")
            
            lines_created = 0
            lines_skipped = 0

            for _, row in entries_df.iterrows():
                # Verificar si ya existe una línea con esta referencia
                existing_line = self.models.execute_kw(
                    self.db, self.uid, self.password,
                    'account.bank.statement.line', 'search_read',
                    [[
                        ('journal_id', '=', journal_id),
                        ('payment_ref', '=', row['Etiqueta'])
                    ]],
                    {'fields': ['id']}
                )

                if existing_line:
                    lines_skipped += 1
                    print(f"Línea existente, omitiendo: {row['Etiqueta']}")
                    continue

                # Convertir la fecha al formato correcto
                if isinstance(row['Fecha'], str):
                    date = datetime.strptime(row['Fecha'], '%Y-%m-%d').strftime('%Y-%m-%d')
                else:
                    date = row['Fecha'].strftime('%Y-%m-%d')

                # Crear la línea de extracto bancario
                line_vals = {
                    'date': date,
                    'payment_ref': row['Etiqueta'],
                    'amount': float(row['Importe']),
                    'journal_id': journal_id,
                }

                print(f"Intentando crear línea con valores: {line_vals}")
                try:
                    new_line = self.models.execute_kw(
                        self.db, self.uid, self.password,
                        'account.bank.statement.line', 'create',
                        [line_vals]
                    )
                    print(f"Línea creada con ID: {new_line}")
                    lines_created += 1
                except Exception as e:
                    print(f"Error al crear línea: {str(e)}")
                    raise

                if new_line:
                    try:
                        # Extraer el número de orden de la etiqueta
                        order_number = row['Etiqueta'].split(' - ')[0].strip()
                        
                        # Buscar asientos contables que contengan el número de orden y el mismo importe
                        matching_moves = self.models.execute_kw(
                            self.db, self.uid, self.password,
                            'account.move.line', 'search_read',
                            [[
                                ('name', 'ilike', order_number),
                                ('debit', '=', float(abs(row['Importe']))) if row['Importe'] > 0 
                                else ('credit', '=', float(abs(row['Importe']))),
                                ('reconciled', '=', False)
                            ]],
                            {'fields': ['id', 'name', 'debit', 'credit']}
                        )

                        if matching_moves:
                            # Preparar los datos para la conciliación
                            reconciliation_vals = {
                                'payment_aml_ids': [(6, 0, [matching_moves[0]['id']])],  # Asientos contables a conciliar
                                'new_aml_dicts': [],  # No creamos nuevos asientos
                            }

                            # Ejecutar la conciliación
                            self.models.execute_kw(
                                self.db, self.uid, self.password,
                                'account.bank.statement.line',
                                'process_reconciliation',
                                [new_line],
                                {'payment_aml_ids': [(6, 0, [matching_moves[0]['id']])]}
                            )
                            print(f"Línea conciliada exitosamente: {row['Etiqueta']}")
                        else:
                            print(f"No se encontró asiento contable para conciliar: {row['Etiqueta']}")

                    except Exception as e:
                        print(f"Error al conciliar la línea {row['Etiqueta']}: {str(e)}")

            return f"Proceso completado: {lines_created} líneas creadas, {lines_skipped} omitidas por ser duplicadas"

        except Exception as e:
            print(f"Error en create_journal_entries: {str(e)}")
            return f"Error al crear las líneas: {str(e)}"

    def read_journals(self):
        """
        Lee todos los diarios contables existentes en Odoo.
        
        :return: Dictionary con los diarios y sus IDs, o mensaje de error
        """
        try:
            journals = self.models.execute_kw(
                self.db, self.uid, self.password,
                'account.journal', 'search_read',
                [[]], 
                {'fields': ['id', 'name', 'type', 'code']}
            )
            
            if not journals:
                return "No se encontraron diarios contables"
            
            return journals

        except Exception as e:
            return f"Error al leer los diarios: {str(e)}"

    def read_unreconciled_bank_statements(self, journal_name=None):
        """
        Lee las líneas de extracto bancario que no están conciliadas.
        
        Args:
            journal_name (str, optional): Nombre del diario para filtrar. Si es None, lee de todos los diarios.
        
        Returns:
            list: Lista de líneas no conciliadas o mensaje de error
        """
        try:
            domain = [('is_reconciled', '=', False)]
            
            if journal_name:
                journal = self.models.execute_kw(
                    self.db, self.uid, self.password,
                    'account.journal', 'search_read',
                    [[['name', '=', journal_name]]],
                    {'fields': ['id']}
                )
                if not journal:
                    return f"No se encontró el diario {journal_name}"
                domain.append(('journal_id', '=', journal[0]['id']))

            statements = self.models.execute_kw(
                self.db, self.uid, self.password,
                'account.bank.statement.line', 'search_read',
                [domain],
                {'fields': ['date', 'payment_ref', 'amount', 'journal_id', 'id']}
            )
            
            if not statements:
                return "No se encontraron líneas sin conciliar"
            
            return statements

        except Exception as e:
            return f"Error al leer las líneas no conciliadas: {str(e)}"

    def read_unreconciled_bank_entry(self, journal_name=None):
        """
        Lee los asientos contables que no están conciliados.
        
        Args:
            journal_name (str, optional): Nombre del diario para filtrar. Si es None, lee de todos los diarios.
        
        Returns:
            list: Lista de asientos no conciliados o mensaje de error
        """
        try:
            domain = [
                ('reconciled', '=', False),
                ('account_type', 'not in', ['asset_receivable', 'liability_payable']),
                ('parent_state', '=', 'posted')
            ]
            
            if journal_name:
                journal = self.models.execute_kw(
                    self.db, self.uid, self.password,
                    'account.journal', 'search_read',
                    [[['name', '=', journal_name]]],
                    {'fields': ['id']}
                )
                if not journal:
                    return f"No se encontró el diario {journal_name}"
                domain.append(('journal_id', '=', journal[0]['id']))

            moves = self.models.execute_kw(
                self.db, self.uid, self.password,
                'account.move.line', 'search_read',
                [domain],
                {
                    'fields': [
                        'date', 
                        'name', 
                        'debit', 
                        'credit',
                        'journal_id',
                        'move_id',
                        'account_id'
                    ]
                }
            )
            
            if not moves:
                return "No se encontraron asientos sin conciliar"
            
            return moves

        except Exception as e:
            return f"Error al leer los asientos no conciliados: {str(e)}"

    #AUX
    def reconcile_statement_line(self, statement_line_id, move_line_id):
        """
        Actualiza el contacto de una línea de extracto bancario y la concilia con el apunte contable.
        
        Args:
            statement_line_id (int): ID de la línea del extracto bancario
            move_line_id (int): ID del apunte contable específico
        """
        try:
            # Verificar y obtener información del apunte contable objetivo (Recibos pendientes)
            target_line = self.models.execute_kw(
                self.db, self.uid, self.password,
                'account.move.line', 'search_read',
                [[('id', '=', move_line_id)]],
                {'fields': ['id', 'partner_id', 'name', 'account_id', 'move_id']}
            )[0]
            
            # Buscar la línea transitoria relacionada al extracto bancario
            transitional_line = self.models.execute_kw(
                self.db, self.uid, self.password,
                'account.move.line', 'search_read',
                [[
                    ('statement_line_id', '=', statement_line_id),
                    ('account_id.code', '=', '110103')  # Cuenta transitoria
                ]],
                {'fields': ['id', 'move_id']}
            )[0]
            
            # Actualizar la línea transitoria con la cuenta de recibos pendientes
            self.models.execute_kw(
                self.db, self.uid, self.password,
                'account.move.line',
                'write',
                [[transitional_line['id']], {
                    'partner_id': target_line['partner_id'][0],
                    'name': target_line['name'],
                    'account_id': target_line['account_id'][0]  # Cuenta de recibos pendientes
                }]
            )
            
            # Actualizar el contacto en la línea de cobranza flow
            flow_lines = self.models.execute_kw(
                self.db, self.uid, self.password,
                'account.move.line', 'search_read',
                [[
                    ('statement_line_id', '=', statement_line_id),
                    ('account_id.code', '=', '1104201')  # Cuenta Cobranza Flow
                ]],
                {'fields': ['id']}
            )
            
            if flow_lines:
                self.models.execute_kw(
                    self.db, self.uid, self.password,
                    'account.move.line',
                    'write',
                    [[flow_lines[0]['id']], {
                        'partner_id': target_line['partner_id'][0]
                    }]
                )
            
            # Actualizar el contacto en el extracto bancario
            self.models.execute_kw(
                self.db, self.uid, self.password,
                'account.bank.statement.line',
                'write',
                [[statement_line_id], {
                    'partner_id': target_line['partner_id'][0]
                }]
            )
            
            # Obtener el apunte contable que queremos conciliar (el que tiene la cuenta de recibos pendientes)
            statement_lines_to_reconcile = self.models.execute_kw(
                self.db, self.uid, self.password,
                'account.move.line', 'search',
                [[
                    ('statement_line_id', '=', statement_line_id),
                    ('account_id', '=', target_line['account_id'][0])
                ]]
            )
            
            # Realizar la conciliación entre los apuntes contables
            if statement_lines_to_reconcile:
                self.models.execute_kw(
                    self.db, self.uid, self.password,
                    'account.move.line',
                    'account_partial_reconcile',
                    [],
                    {
                        'debit_move_id': move_line_id,
                        'credit_move_id': statement_lines_to_reconcile[0]
                    }
                )
            
            return True
                
        except Exception as e:
            return f"Error durante la actualización: {str(e)}"

# Prueba de actualización con IDs específicos
odoo_journal = OdooJournal(database='test')

# IDs específicos para probar
statement_line_id = 11356  # ID del extracto bancario
move_line_id = 285476  # ID del apunte contable específico

print(f"\nProbando actualización de contacto con:")
print(f"Statement Line ID: {statement_line_id}")
print(f"Move Line ID: {move_line_id}")

try:
    result = odoo_journal.reconcile_statement_line(
        statement_line_id=statement_line_id,
        move_line_id=move_line_id
    )
    
    if isinstance(result, str):
        print(f"\n❌ Error en la actualización: {result}")
    else:
        print("\n✓ Actualización de contacto exitosa")
except Exception as e:
    print(f"Error en la ejecución: {str(e)}")
        
