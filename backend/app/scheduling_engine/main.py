from .sample_data_fixed import get_dataset

data = get_dataset("valid")

employees = data["employees"]
brands = data["brands"]
assignments = data["employee_assignments"]
processes = data["processes"]

print("Total Employees:", len(employees))
print("Total Brands:", len(brands))
print("Total Employee Assignments:", len(assignments))

print("\nEmployees:")
for employee in employees:
    print(employee["employee_id"], employee["name"])

print("\Brands:")
for brand in brands:
    print(brand["brand_id"], brand["brand_name"])

print("\Process:")
for p in processes:
    print(p["process_id"], p["process_name"])