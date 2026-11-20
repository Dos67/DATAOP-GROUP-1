from django.shortcuts import render, redirect
from django.db import connection
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import Group
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test


def home(request):
    return render(request, 'reports/home.html')


def sales_report(request):
    # Available years for the filter
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT DISTINCT YEAR(OrderDate) AS SalesYear
            FROM Sales.SalesOrderHeader
            ORDER BY SalesYear;
        """)
        years = [row[0] for row in cursor.fetchall()]

    # Get the selected year from the dropdown
    selected_year = request.GET.get('year', '')

    if selected_year not in [str(year) for year in years]:
        selected_year = ''

    selected_year_value = int(selected_year) if selected_year else None

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT
                YEAR(OrderDate) AS SalesYear,
                COUNT(SalesOrderID) AS TotalOrders,
                SUM(SubTotal) AS TotalSales
            FROM Sales.SalesOrderHeader
            GROUP BY YEAR(OrderDate)
            ORDER BY SalesYear;
        """)

        rows = cursor.fetchall()

    sales_data = [
        {
            'year': row[0],
            'total_orders': row[1],
            'total_sales': float(row[2] or 0),
            'total_sales_formatted': f"{float(row[2] or 0):,.2f}",
        }
        for row in rows
    ]


    # Sales by Territory
    with connection.cursor() as cursor:
        if selected_year_value is not None:
            cursor.execute("""
                SELECT
                    st.Name AS Territory,
                    SUM(soh.SubTotal) AS TotalSales
                FROM Sales.SalesOrderHeader AS soh
                INNER JOIN Sales.SalesTerritory AS st
                    ON soh.TerritoryID = st.TerritoryID
                WHERE YEAR(soh.OrderDate) = %s
                GROUP BY st.Name
                ORDER BY TotalSales DESC;
            """, [selected_year_value])
        else:
            cursor.execute("""
                SELECT
                    st.Name AS Territory,
                    SUM(soh.SubTotal) AS TotalSales
                FROM Sales.SalesOrderHeader AS soh
                INNER JOIN Sales.SalesTerritory AS st
                    ON soh.TerritoryID = st.TerritoryID
                GROUP BY st.Name
                ORDER BY TotalSales DESC;
            """)

        territory_rows = cursor.fetchall()


    territory_data = [
        {
            'territory': row[0],
            'total_sales': float(row[1] or 0),
        }
        for row in territory_rows
    ]


    # Sales by Product Category
    with connection.cursor() as cursor:
        if selected_year_value is not None:
            cursor.execute("""
                SELECT
                    pc.Name AS Category,
                    SUM(sod.LineTotal) AS TotalSales
                FROM Sales.SalesOrderDetail AS sod
                INNER JOIN Sales.SalesOrderHeader AS soh
                    ON sod.SalesOrderID = soh.SalesOrderID
                INNER JOIN Production.Product AS p
                    ON sod.ProductID = p.ProductID
                INNER JOIN Production.ProductSubcategory AS psc
                    ON p.ProductSubcategoryID = psc.ProductSubcategoryID
                INNER JOIN Production.ProductCategory AS pc
                    ON psc.ProductCategoryID = pc.ProductCategoryID
                WHERE YEAR(soh.OrderDate) = %s
                GROUP BY pc.Name
                ORDER BY TotalSales DESC;
            """, [selected_year_value])
        else:
            cursor.execute("""
                SELECT
                    pc.Name AS Category,
                    SUM(sod.LineTotal) AS TotalSales
                FROM Sales.SalesOrderDetail AS sod
                INNER JOIN Sales.SalesOrderHeader AS soh
                    ON sod.SalesOrderID = soh.SalesOrderID
                INNER JOIN Production.Product AS p
                    ON sod.ProductID = p.ProductID
                INNER JOIN Production.ProductSubcategory AS psc
                    ON p.ProductSubcategoryID = psc.ProductSubcategoryID
                INNER JOIN Production.ProductCategory AS pc
                    ON psc.ProductCategoryID = pc.ProductCategoryID
                GROUP BY pc.Name
                ORDER BY TotalSales DESC;
            """)

        category_rows = cursor.fetchall()


    category_data = [
        {
            'category': row[0],
            'total_sales': float(row[1] or 0),
        }
        for row in category_rows
    ]

    return render(request, 'reports/sales_report.html', {
        'sales_data': sales_data,
        'territory_data': territory_data,
        'category_data': category_data,
        'years': years,
        'selected_year': selected_year,
    })


def customer_profile(request):
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT TOP 20
                c.CustomerID,
                COALESCE(
                    NULLIF(
                        LTRIM(RTRIM(CONCAT(p.FirstName, ' ', p.LastName))),
                        ''
                    ),
                    s.Name,
                    'Unknown'
                ) AS CustomerName,
                CASE
                    WHEN c.StoreID IS NOT NULL THEN 'Store'
                    WHEN c.PersonID IS NOT NULL THEN 'Individual'
                    ELSE 'Other'
                END AS CustomerType,
                COUNT(soh.SalesOrderID) AS TotalOrders,
                SUM(soh.SubTotal) AS TotalSales
            FROM Sales.Customer AS c
            INNER JOIN Sales.SalesOrderHeader AS soh
                ON c.CustomerID = soh.CustomerID
            LEFT JOIN Person.Person AS p
                ON c.PersonID = p.BusinessEntityID
            LEFT JOIN Sales.Store AS s
                ON c.StoreID = s.BusinessEntityID
            GROUP BY
                c.CustomerID,
                p.FirstName,
                p.LastName,
                s.Name,
                c.StoreID,
                c.PersonID
            ORDER BY TotalSales DESC;
        """)

        rows = cursor.fetchall()

    customer_data = [
        {
            'customer_id': row[0],
            'customer_name': row[1],
            'customer_type': row[2],
            'total_orders': row[3],
            'total_sales': float(row[4] or 0),
            'total_sales_formatted': f"{float(row[4] or 0):,.2f}",
        }
        for row in rows
    ]

    return render(request, 'reports/customer_profile.html', {
        'customer_data': customer_data,
    })


def revenue_loss_report(request):
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT
                YEAR(soh.OrderDate) AS SalesYear,
                COUNT(DISTINCT soh.SalesOrderID) AS TotalOrders,
                SUM(sod.LineTotal) AS TotalRevenue,
                SUM(p.StandardCost * sod.OrderQty) AS EstimatedCost,
                SUM(sod.LineTotal) -
                    SUM(p.StandardCost * sod.OrderQty) AS EstimatedProfitLoss
            FROM Sales.SalesOrderHeader AS soh
            INNER JOIN Sales.SalesOrderDetail AS sod
                ON soh.SalesOrderID = sod.SalesOrderID
            INNER JOIN Production.Product AS p
                ON sod.ProductID = p.ProductID
            GROUP BY YEAR(soh.OrderDate)
            ORDER BY SalesYear;
        """)

        rows = cursor.fetchall()

    revenue_loss_data = [
        {
            'year': row[0],
            'total_orders': row[1],
            'total_revenue': float(row[2] or 0),
            'total_revenue_formatted': f"{float(row[2] or 0):,.2f}",
            'estimated_cost': float(row[3] or 0),
            'estimated_cost_formatted': f"{float(row[3] or 0):,.2f}",
            'estimated_profit_loss': float(row[4] or 0),
            'estimated_profit_loss_formatted': f"{float(row[4] or 0):,.2f}",
        }
        for row in rows
    ]

    return render(request, 'reports/revenue_loss_report.html', {
        'revenue_loss_data': revenue_loss_data,
    })


def cost_report(request):
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT
                p.ProductID,
                p.Name AS ProductName,
                COALESCE(pc.Name, 'Uncategorized') AS Category,
                p.StandardCost,
                p.ListPrice,
                CASE
                    WHEN p.ListPrice > 0 THEN
                        ((p.ListPrice - p.StandardCost) / p.ListPrice) * 100
                    ELSE 0
                END AS EstimatedProfitMargin
            FROM Production.Product AS p
            LEFT JOIN Production.ProductSubcategory AS psc
                ON p.ProductSubcategoryID = psc.ProductSubcategoryID
            LEFT JOIN Production.ProductCategory AS pc
                ON psc.ProductCategoryID = pc.ProductCategoryID
            ORDER BY p.Name;
        """)

        rows = cursor.fetchall()

    cost_data = [
        {
            'product_id': row[0],
            'product_name': row[1],
            'category': row[2],
            'standard_cost': float(row[3] or 0),
            'standard_cost_formatted': f"{float(row[3] or 0):,.2f}",
            'list_price': float(row[4] or 0),
            'list_price_formatted': f"{float(row[4] or 0):,.2f}",
            'profit_margin': float(row[5] or 0),
            'profit_margin_formatted': f"{float(row[5] or 0):,.2f}",
        }
        for row in rows
    ]

    return render(request, 'reports/cost_report.html', {
        'cost_data': cost_data,
    })

