try:
    import pyodbc
    PYODBC_AVAILABLE = True
except ImportError:
    PYODBC_AVAILABLE = False
    print("[Database] Warning: pyodbc not installed. Database functionality will be limited.")

import openai
from utils.config import Config
from typing import Optional, List, Dict, Any

class Database:
    def __init__(self):
        """Initialize connection to SQL Server database"""
        if not PYODBC_AVAILABLE:
            self.conn = None
            print("[Database] pyodbc is not available. Please install it with: pip install pyodbc")
            return
            
        self.connection_string = (
            "Driver={ODBC Driver 17 for SQL Server};"
            "Server=ITCS-AWAIS\\SQLEXPRESS;"
            "Database=ITCS;"
            "Trusted_Connection=yes;"
        )
        self.conn = None
        self.client = openai.AzureOpenAI(
            api_key=Config.OPENAI_API_KEY,
            api_version="2024-02-15-preview",
            azure_endpoint=Config.OPENAI_ENDPOINT
        )
        self._connect()

    def _connect(self):
        """Establish connection to the database"""
        if not PYODBC_AVAILABLE:
            self.conn = None
            return
        try:
            self.conn = pyodbc.connect(self.connection_string)
            self.conn.setdecoding(pyodbc.SQL_CHAR, encoding='utf-8')
            self.conn.setdecoding(pyodbc.SQL_WCHAR, encoding='utf-8')
            self.conn.setencoding(encoding='utf-8')
        except Exception as e:
            print(f"[Database] Connection error: {e}")
            self.conn = None

    def _ensure_connection(self):
        """Ensure database connection is active, reconnect if needed"""
        if self.conn is None:
            self._connect()
        try:
            # Test connection
            self.conn.execute("SELECT 1")
        except Exception:
            self._connect()

    def execute_query(self, query: str) -> Optional[List[Dict[str, Any]]]:
        """Execute a SQL query and return results as a list of dictionaries"""
        if not self.conn:
            raise Exception("Database connection not available")
        
        try:
            self._ensure_connection()
            cursor = self.conn.cursor()
            cursor.execute(query)
            
            # Get column names
            columns = [column[0] for column in cursor.description]
            
            # Fetch all rows and convert to dictionaries
            rows = cursor.fetchall()
            results = []
            for row in rows:
                results.append(dict(zip(columns, row)))
            
            cursor.close()
            return results
        except Exception as e:
            print(f"[Database] Query error: {e}")
            # Re-raise the exception so callers can handle it
            raise

    def get_table_names(self) -> List[str]:
        """Get list of all table names in the database with schema prefixes"""
        query = """
            SELECT TABLE_SCHEMA + '.' + TABLE_NAME AS FULL_TABLE_NAME
            FROM INFORMATION_SCHEMA.TABLES 
            WHERE TABLE_TYPE = 'BASE TABLE'
            ORDER BY TABLE_SCHEMA, TABLE_NAME
        """
        results = self.execute_query(query)
        if results:
            return [row['FULL_TABLE_NAME'] for row in results]
        return []

    def get_table_schema(self, table_name: str) -> Optional[List[Dict[str, Any]]]:
        """Get schema information for a specific table (can be schema.table or just table)"""
        # Handle both schema.table and just table name
        if '.' in table_name:
            schema, table = table_name.split('.', 1)
            query = """
                SELECT 
                    COLUMN_NAME,
                    DATA_TYPE,
                    IS_NULLABLE,
                    CHARACTER_MAXIMUM_LENGTH
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ?
                ORDER BY ORDINAL_POSITION
            """
            try:
                self._ensure_connection()
                cursor = self.conn.cursor()
                cursor.execute(query, (schema, table))
                columns = [column[0] for column in cursor.description]
                rows = cursor.fetchall()
                results = [dict(zip(columns, row)) for row in rows]
                cursor.close()
                return results
            except Exception as e:
                print(f"[Database] Schema error: {e}")
                return None
        else:
            query = """
                SELECT 
                    COLUMN_NAME,
                    DATA_TYPE,
                    IS_NULLABLE,
                    CHARACTER_MAXIMUM_LENGTH
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_NAME = ?
                ORDER BY ORDINAL_POSITION
            """
            try:
                self._ensure_connection()
                cursor = self.conn.cursor()
                cursor.execute(query, (table_name,))
                columns = [column[0] for column in cursor.description]
                rows = cursor.fetchall()
                results = [dict(zip(columns, row)) for row in rows]
                cursor.close()
                return results
            except Exception as e:
                print(f"[Database] Schema error: {e}")
                return None

    def get_tables_with_schemas(self, table_names: List[str], limit: int = 10) -> Dict[str, List[str]]:
        """Get column names for multiple tables"""
        tables_schemas = {}
        for table_name in table_names[:limit]:
            schema_info = self.get_table_schema(table_name)
            if schema_info:
                columns = [col['COLUMN_NAME'] for col in schema_info]
                tables_schemas[table_name] = columns
        return tables_schemas

    def find_attendance_table(self) -> Optional[Dict[str, Any]]:
        """Find the attendance table by looking for tables with attendance-related data"""
        try:
            tables = self.get_table_names()
            for table in tables:
                # Get a sample row to check if it contains attendance data
                try:
                    sample_query = f"SELECT TOP 1 * FROM {table}"
                    sample = self.execute_query(sample_query)
                    if sample and len(sample) > 0:
                        row = sample[0]
                        # Check if row contains attendance-related values
                        values = [str(v).lower() if v else '' for v in row.values()]
                        if any(val in ['present', 'leave', 'late', 'wfh', 'half leave'] for val in values):
                            # Get full schema
                            schema_info = self.get_table_schema(table)
                            if schema_info:
                                columns = [col['COLUMN_NAME'] for col in schema_info]
                                return {
                                    'table_name': table,
                                    'columns': columns,
                                    'sample_row': row
                                }
                except:
                    continue
        except Exception as e:
            print(f"[Database] Error finding attendance table: {e}")
        return None

    def query_with_summary(self, query: str, max_rows: int = 100) -> str:
        """Execute a query and generate a short summary using OpenAI"""
        try:
            results = self.execute_query(query)
        except Exception as e:
            error_msg = str(e)
            if "Invalid object name" in error_msg:
                # Extract table name from error for better user feedback
                import re
                match = re.search(r"Invalid object name '([^']+)'", error_msg)
                if match:
                    table_name = match.group(1)
                    return f"Sorry, the table '{table_name}' was not found. Please check if the table name is correct and includes the schema prefix (e.g., Person.Person)."
            return f"Sorry, I encountered an error executing the query: {error_msg}"
        
        if results is None:
            return "Sorry, I couldn't connect to the database."
        
        if not results:
            return "The query returned no results."
        
        # Limit results for summary generation
        limited_results = results[:max_rows]
        
        # Convert results to a readable format
        if len(limited_results) == 0:
            return "No data found."
        
        # Create a summary string from the results
        result_summary = f"Query returned {len(results)} row(s). "
        
        # If only one row, provide detailed summary
        if len(limited_results) == 1:
            row = limited_results[0]
            summary_parts = [f"{key}: {value}" for key, value in row.items()]
            result_summary += "Result: " + ", ".join(summary_parts) + "."
        else:
            # For multiple rows, use OpenAI to generate a concise summary
            try:
                # Prepare data for summarization
                data_preview = str(limited_results[:10])  # First 10 rows for context
                
                prompt = f"""You are a database query assistant. Summarize the following query results in a very short, concise way (1-2 sentences max). 
Focus on key insights, patterns, or important numbers.

Query Results (showing first {min(10, len(limited_results))} of {len(results)} rows):
{data_preview}

Provide a brief summary:"""
                
                response = self.client.chat.completions.create(
                    model=Config.OPENAI_DEPLOYMENT_NAME,
                    messages=[
                        {"role": "system", "content": "You are a concise database query summarizer. Always respond in 1-2 short sentences."},
                        {"role": "user", "content": prompt}
                    ],
                    max_completion_tokens=100
                )
                
                ai_summary = response.choices[0].message.content.strip()
                result_summary += ai_summary
                
                if len(results) > max_rows:
                    result_summary += f" (Showing summary of first {max_rows} rows, {len(results)} total rows found.)"
                    
            except Exception as e:
                print(f"[Database] Summary generation error: {e}")
                # Fallback to simple summary
                result_summary += f"Found {len(results)} record(s) with {len(limited_results[0])} columns each."
        
        return result_summary

    def auto_query(self, user_request: str) -> str:
        """Automatically generate and execute a query based on user request, then return summary"""
        if not PYODBC_AVAILABLE:
            return "Sorry, database functionality is not available. Please install pyodbc: pip install pyodbc"
        if not self.conn:
            return "Sorry, I couldn't connect to the database. Please check your connection settings."
        try:
            # First, try to find the attendance table automatically
            attendance_info = self.find_attendance_table()
            
            if attendance_info:
                # We found the attendance table - use it directly
                table_name = attendance_info['table_name']
                columns = attendance_info['columns']
                sample_row = attendance_info['sample_row']
                
                # Identify name column and date columns
                name_column = None
                date_columns = []
                
                for col in columns:
                    col_lower = col.lower()
                    if any(name_word in col_lower for name_word in ['name', 'employee', 'staff', 'person']):
                        name_column = col
                    # Date columns are those that contain attendance values
                    if col in sample_row:
                        val = str(sample_row[col]).lower() if sample_row[col] else ''
                        if val in ['present', 'leave', 'late', 'wfh', 'half leave', 'absent']:
                            date_columns.append(col)
                
                # Build a specialized prompt for attendance queries
                columns_str = ", ".join(columns)
                date_cols_str = ", ".join(date_columns) if date_columns else "date columns"
                
                prompt = f"""You are generating SQL queries for an ATTENDANCE/LEAVE tracking database.

TABLE: {table_name}
ALL COLUMNS: {columns_str}
NAME COLUMN (for filtering by employee name): {name_column or 'first column that looks like a name'}
DATE/ATTENDANCE COLUMNS (contain values: Present, Leave, Late, WFH, Half Leave, Absent, NULL): {date_cols_str}

USER REQUEST: "{user_request}"

ATTENDANCE QUERY MAPPING:
- "How many leaves did [Name] get?" = Count how many times 'Leave' appears across ALL date columns for that person
  Use: SELECT SUM(CASE WHEN [col1] = 'Leave' THEN 1 ELSE 0 END + CASE WHEN [col2] = 'Leave' THEN 1 ELSE 0 END + ...) AS LeaveCount 
       FROM {table_name} WHERE {name_column} LIKE '%[Name]%'
  
- "How many days late did [Name]?" = Count how many times 'Late' appears across ALL date columns
  Use: SELECT SUM(CASE WHEN [col1] = 'Late' THEN 1 ELSE 0 END + CASE WHEN [col2] = 'Late' THEN 1 ELSE 0 END + ...) AS LateDays
       FROM {table_name} WHERE {name_column} LIKE '%[Name]%'
  
- "Who was late on [day/column]?" = SELECT {name_column} WHERE the specific date column = 'Late'
  If user says "on 27", check if there's a column with "27" in the name, or use column position/index
  
- "How many employees present on [day/column]?" = COUNT(*) WHERE the specific date column = 'Present'
  
- For counting across multiple columns, you MUST sum up CASE statements for EACH date column

CRITICAL RULES:
1. Use table name: {table_name}
2. Use name column: {name_column or 'identify from columns list'}
3. Use date columns: {date_cols_str or 'all columns except name and ID'}
4. For name matching, use LIKE '%Name%' for partial matches
5. For counting leaves/late across multiple date columns, use OR conditions or SUM with CASE
6. Return ONLY the SQL query, no explanations

SQL Query:"""
                
                response = self.client.chat.completions.create(
                    model=Config.OPENAI_DEPLOYMENT_NAME,
                    messages=[
                        {"role": "system", "content": "You are a SQL query generator for attendance/leave tracking. Return only valid SQL queries using exact table and column names."},
                        {"role": "user", "content": prompt}
                    ],
                    max_completion_tokens=400
                )
                
                sql_query = response.choices[0].message.content.strip()
                
                # Clean up
                if sql_query.startswith("```"):
                    sql_query = sql_query.split("```")[1]
                    if sql_query.startswith("sql"):
                        sql_query = sql_query[3:]
                sql_query = sql_query.rstrip(';').strip()
                
                print(f"[Database] Generated SQL (attendance table): {sql_query}")
                
                try:
                    summary = self.query_with_summary(sql_query)
                    return summary
                except Exception as query_error:
                    error_str = str(query_error)
                    print(f"[Database] Query error: {error_str}")
                    return f"Sorry, I encountered an error: {error_str}. Please try rephrasing your question."
            
            # Fallback to original method if no attendance table found
            tables = self.get_table_names()
            if not tables:
                return "No tables found in the database."
            
            # Find attendance/employee related tables (might be in any schema)
            attendance_tables = []
            for table in tables:
                table_lower = table.lower()
                if any(keyword in table_lower for keyword in ['attendance', 'employee', 'staff', 'leave', 'present', 'late']):
                    attendance_tables.append(table)
            
            # If no specific attendance tables found, get all tables
            if not attendance_tables:
                common_tables = [t for t in tables if any(schema in t for schema in ['Sales', 'Production', 'HumanResources', 'Person', 'Purchasing'])]
                if len(common_tables) > 15:
                    tables_to_show = common_tables[:15]
                else:
                    tables_to_show = tables[:20] if len(tables) > 20 else tables
            else:
                tables_to_show = attendance_tables[:10] + [t for t in tables if t not in attendance_tables][:10]
            
            # Get actual column information for ALL relevant tables (not limited)
            tables_schemas = self.get_tables_with_schemas(tables_to_show, limit=len(tables_to_show))
            
            # Build schema information string - include ALL columns for attendance-related tables
            schema_info_parts = []
            for table_name, columns in tables_schemas.items():
                # For attendance tables, show ALL columns; for others, limit to 20
                is_attendance = any(keyword in table_name.lower() for keyword in ['attendance', 'employee', 'staff', 'leave'])
                if is_attendance:
                    columns_str = ", ".join(columns)  # ALL columns for attendance tables
                else:
                    columns_str = ", ".join(columns[:20])
                    if len(columns) > 20:
                        columns_str += f" (and {len(columns) - 20} more columns)"
                schema_info_parts.append(f"{table_name}: columns are [{columns_str}]")
            
            schema_info = "\n".join(schema_info_parts)
            tables_list = ", ".join(tables_to_show)
            
            # Log the generated query for debugging
            print(f"[Database] User request: {user_request}")
            print(f"[Database] Found {len(tables_schemas)} tables with schemas")
            
            # Build a more intelligent prompt that helps map user intent to tables
            prompt = f"""You are an expert SQL Server query generator. Your task is to understand the user's request and generate an accurate SQL query using ONLY the actual table and column names provided below.

AVAILABLE TABLES: {tables_list}

TABLE SCHEMAS (ACTUAL COLUMN NAMES - YOU MUST USE ONLY THESE EXACT NAMES):
{schema_info}

USER REQUEST: "{user_request}"

CRITICAL INSTRUCTIONS FOR ATTENDANCE/LEAVE QUERIES:
- "How many leaves did [Name] get?" = COUNT rows WHERE name column contains [Name] AND any date column = 'Leave'
- "How many days late did [Name]?" = COUNT rows WHERE name column contains [Name] AND any date column = 'Late'
- "Who was late on [day/column]?" = SELECT name WHERE the specific day/column = 'Late'
- "How many employees present on [day/column]?" = COUNT WHERE the specific day/column = 'Present'
- "leaves" or "leave" means counting occurrences of the value 'Leave' in date columns
- "late" means counting occurrences of the value 'Late' in date columns
- "present" means the value 'Present' in date columns
- When user says "on 27" or similar, they might mean column index/position or a specific date column
- Name matching should use LIKE '%Name%' or exact match depending on the column

GENERAL QUERY GENERATION RULES:
1. ALWAYS use schema-qualified table names if schema exists (e.g., Schema.TableName)
2. USE ONLY the exact column names listed above - NEVER invent, guess, or abbreviate column names
3. For counting: Use COUNT(*) or COUNT(column) with appropriate WHERE clauses
4. For filtering by name: Use WHERE column_name LIKE '%Name%' or = 'Name' depending on exact match needed
5. For counting values across columns: You may need to count each column separately and sum, or use CASE statements
6. Use proper SQL Server syntax
7. Only SELECT queries (no INSERT, UPDATE, DELETE)
8. Return ONLY the SQL query, no explanations, no markdown, no code blocks, no backticks

SQL Query:"""
            
            response = self.client.chat.completions.create(
                model=Config.OPENAI_DEPLOYMENT_NAME,
                messages=[
                    {"role": "system", "content": "You are a SQL query generator. Return only valid SQL queries."},
                    {"role": "user", "content": prompt}
                ],
                max_completion_tokens=300
            )
            
            sql_query = response.choices[0].message.content.strip()
            
            # Clean up the query (remove markdown code blocks if present)
            if sql_query.startswith("```"):
                sql_query = sql_query.split("```")[1]
                if sql_query.startswith("sql"):
                    sql_query = sql_query[3:]
                sql_query = sql_query.strip()
            
            # Remove trailing semicolons and clean up
            sql_query = sql_query.rstrip(';').strip()
            
            # Log the generated query for debugging
            print(f"[Database] Generated SQL: {sql_query}")
            
            # Try to fix common schema issues - if query fails, try adding schema prefixes
            try:
                # Execute the query and get summary
                summary = self.query_with_summary(sql_query)
                return summary
            except Exception as query_error:
                error_str = str(query_error)
                import re
                
                # If it's a column name error, try to fix it
                if "Invalid column name" in error_str:
                    match = re.search(r"Invalid column name '([^']+)'", error_str)
                    if match:
                        invalid_column = match.group(1)
                        # Try to find the correct column by querying the table schema
                        # Extract table name from the query
                        table_match = re.search(r'FROM\s+([\w\.]+)', sql_query, re.IGNORECASE)
                        if table_match:
                            table_name = table_match.group(1)
                            # Get actual columns for this table
                            schema_info = self.get_table_schema(table_name)
                            if schema_info:
                                actual_columns = [col['COLUMN_NAME'] for col in schema_info]
                                # Try to find a similar column name
                                similar_col = None
                                invalid_lower = invalid_column.lower()
                                for col in actual_columns:
                                    if invalid_lower in col.lower() or col.lower() in invalid_lower:
                                        similar_col = col
                                        break
                                
                                if similar_col:
                                    # Replace the invalid column with the correct one
                                    sql_query = re.sub(
                                        r'\b' + re.escape(invalid_column) + r'\b',
                                        similar_col,
                                        sql_query,
                                        flags=re.IGNORECASE
                                    )
                                    print(f"[Database] Fixed column name: {invalid_column} -> {similar_col}")
                                    try:
                                        summary = self.query_with_summary(sql_query)
                                        return summary
                                    except Exception as retry_error:
                                        print(f"[Database] Retry query error: {retry_error}")
                                
                                # If no similar column, try regenerating the query with correct schema
                                columns_str = ", ".join(actual_columns[:20])
                                retry_prompt = f"""The previous query failed because column '{invalid_column}' doesn't exist in {table_name}.

Actual columns in {table_name}: {columns_str}

User request: {user_request}

Generate a NEW SQL query using ONLY the columns listed above. Use schema-qualified table name {table_name}. Return ONLY the SQL query.

SQL Query:"""
                                
                                try:
                                    retry_response = self.client.chat.completions.create(
                                        model=Config.OPENAI_DEPLOYMENT_NAME,
                                        messages=[
                                            {"role": "system", "content": "You are a SQL query generator. Return only valid SQL queries using the exact column names provided."},
                                            {"role": "user", "content": retry_prompt}
                                        ],
                                        max_completion_tokens=300
                                    )
                                    new_sql = retry_response.choices[0].message.content.strip()
                                    # Clean up
                                    if new_sql.startswith("```"):
                                        new_sql = new_sql.split("```")[1]
                                        if new_sql.startswith("sql"):
                                            new_sql = new_sql[3:]
                                    new_sql = new_sql.rstrip(';').strip()
                                    
                                    summary = self.query_with_summary(new_sql)
                                    return summary
                                except Exception as retry_gen_error:
                                    print(f"[Database] Retry generation error: {retry_gen_error}")
                                
                                # Final fallback
                                return f"Sorry, the column '{invalid_column}' doesn't exist in {table_name}. Available columns: {', '.join(actual_columns[:15])}{'...' if len(actual_columns) > 15 else ''}"
                    
                    return f"Sorry, I encountered a column name error. Please try rephrasing your question more specifically."
                
                # If it's a table name error, try to fix it
                elif "Invalid object name" in error_str:
                    match = re.search(r"Invalid object name '([^']+)'", error_str)
                    if match:
                        table_name = match.group(1)
                        # Try to find the correct schema-qualified name
                        for full_table_name in tables:
                            if full_table_name.split('.')[-1].lower() == table_name.lower():
                                # Replace unqualified name with qualified name
                                sql_query = re.sub(
                                    r'\b' + re.escape(table_name) + r'\b',
                                    full_table_name,
                                    sql_query,
                                    flags=re.IGNORECASE
                                )
                                print(f"[Database] Fixed table name: {table_name} -> {full_table_name}")
                                # Retry the query
                                try:
                                    summary = self.query_with_summary(sql_query)
                                    return summary
                                except Exception as retry_error:
                                    print(f"[Database] Retry query error: {retry_error}")
                                    return f"Sorry, I couldn't execute the query. The table '{table_name}' might not exist or the query syntax is incorrect."
                    return f"Sorry, I couldn't find the table in the database. Please try rephrasing your question."
                else:
                    # For other errors, try to regenerate with better context
                    print(f"[Database] Query error: {error_str}")
                    return f"Sorry, I encountered an error: {error_str}. Please try rephrasing your question more specifically."
            
        except Exception as e:
            print(f"[Database] Auto query error: {e}")
            return f"Sorry, I encountered an error while querying the database: {str(e)}"

    def close(self):
        """Close the database connection"""
        if self.conn:
            try:
                self.conn.close()
            except Exception:
                pass
            self.conn = None

    def __del__(self):
        """Cleanup on deletion"""
        self.close()

