from collections import defaultdict
from sklearn.neighbors import KNeighborsClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline

def attendance_features(records):
    # records: iterable of attendance status strings, oldest to newest
    n = len(records)
    if not n:
        return [0.0, 0.0, 0.0, 0.0]
    present = sum(s == "Present" for s in records)
    absent = sum(s == "Absent" for s in records)
    last7 = records[-7:]
    last30 = records[-30:]
    rate = present / n
    recent7 = sum(s == "Present" for s in last7) / len(last7)
    recent30 = sum(s == "Present" for s in last30) / len(last30)
    absence_rate = absent / n
    return [rate, recent7, recent30, absence_rate]

def train_and_predict(feature_rows):
    """KNN demo classifier. feature_rows: list of (features, label).
    Requires at least 3 labeled historical examples. Labels: Low Risk / High Risk.
    """
    if len(feature_rows) < 3:
        return None
    X = [row[0] for row in feature_rows]
    y = [row[1] for row in feature_rows]
    k = min(3, len(X))
    model = make_pipeline(StandardScaler(), KNeighborsClassifier(n_neighbors=k, weights="distance"))
    model.fit(X, y)
    return model
